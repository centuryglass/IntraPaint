#!/usr/bin/env python3
# Source: http://blog.ssokolow.com/archives/2019/06/01/gui-error-handler-for-pyqt-5-x/
# Adapted from Stephan Sokolow's PyQt 5 exception handler. Local changes: ported to PySide6, blocked dialog
# activation outside the main thread, logs every uncaught exception, shows worker-thread exceptions on the main
# thread, and reports plain tracebacks plus environment details.
"""Logs every uncaught exception and shows it in an error dialog.

Usage::

    app = QApplication(sys.argv)
    QtExceptHook().enable()

Exceptions from any thread are logged with their traceback. The dialog only opens on the main thread, so an exception
from a worker thread is queued there.

Adapted from gtkexcepthook.py::

    (c) 2003 Gustavo J A M Carneiro gjc at inescporto.pt
        2004-2005 Filip Van Raemdonck
        2009, 2011, 2019 Stephan Sokolow

    http://www.daa.com.au/pipermail/pygtk/2003-August/005775.html
    Message-ID: <1062087716.1196.5.camel@emperor.homelinux.net>
        "The license is whatever you want."

Additions copyright 2019, 2020 Stephan Sokolow
"""

__author__ = 'Stephan Sokolow; Filip Van Raemdonck; Gustavo J A M Carneiro'
__license__ = 'Public Domain'

import logging
import sys
import threading
import traceback
from types import TracebackType
from typing import Callable, Optional

# pylint: disable=no-name-in-module
from PySide6.QtCore import (QEvent,
                            Slot)
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import QApplication, QMessageBox, QSizePolicy, QTextEdit

from src.util.main_thread import run_on_main_thread

logger = logging.getLogger(__name__)

#: The :meth:`QCoreApplication.translate` context for strings in this file
TR_ID = 'excepthook'


def _tr(*args):
    """Helper to make :meth:`QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


class ResizableMessageBox(QMessageBox):  # pylint: disable=R0903
    """QMessageBox which allows the detailed text expander to be resized
    and sets it to display non-wrapping monospace text.

    Adapted from `Resizing a QMessageBox?
    <https://www.qtcentre.org/threads/24888-Resizing-a-QMessageBox>`_ on
    Qt Center.

    .. todo:: For some reason, calling :meth:`QWidget.setMaximumSize` in this
        causes KWin to misalign the titlebar's right button box under Kubuntu
        16.04 LTS until the window is moved or resized.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet('QTextEdit { font-family: monospace; }')

    def event(self, event):
        """Override :meth:`QWidget.event` to hook in our customizations *after*
        Qt tries to force settings on us.

        (Use :class:`LayoutRequest <QEvent>` because it only gets fired two to
        four times under typical operation and happens at the right time.)
        """
        res = QMessageBox.event(self, event)

        # Skip events we don't care about
        if event.type() != QEvent.Type.LayoutRequest:
            return res

        # Only do all this stuff once the TextWidget is here
        details = self.findChild(QTextEdit)
        if details:
            self.setSizeGripEnabled(True)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.setMaximumSize(16777215, 16777215)

            details.setWordWrapMode(QTextOption.WrapMode.NoWrap)
            details.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            details.setMaximumSize(16777215, 16777215)

        return res


class QtExceptHook():
    """GUI exception hook for PyQt 5.x applications

    :param reporting_cb: If provided, a :guilabel:`Report bug...` button will
        be added which will call ``reporting_cb`` when clicked.
    :param recovery_cb: If provided, called before the :guilabel:`Quit` button quits. It should preserve the
        user's work for the next launch and return whether it did. The quit button's label says which.
    :param recovery_enabled_cb: Returns whether ``recovery_cb`` can preserve work, for the quit button's label.
    :param extra_info_cb: If provided, returns environment details to append to every report.
    """

    def __init__(self, reporting_cb: Optional[Callable[[str], None]]=None, # type: ignore
                 recovery_cb: Optional[Callable[[], bool]] = None,
                 recovery_enabled_cb: Optional[Callable[[], bool]] = None,
                 extra_info_cb: Optional[Callable[[], str]] = None):
        """Initialize as much as possible on application startup.

        (Maximize the chance that a bug in the exception handling system will
        show up as early as possible.)
        """
        self._extra_info_cb = extra_info_cb
        self._showing = False
        self._reporting_cb = reporting_cb
        self._recovery_cb = recovery_cb
        self._recovery_enabled_cb = recovery_enabled_cb

        self._dialog = ResizableMessageBox(QMessageBox.Icon.Warning,
            _tr('Bug Detected'),
            _tr('<big><b>A programming error has been detected '
                'during the execution of this program.</b></big>'))

        secondary = _tr('It probably isn\'t fatal, but should be '
                        'reported to the developers nonetheless.')

        if self._reporting_cb is not None:
            btn_report = self._dialog.addButton(_tr('Report bug...'), QMessageBox.ButtonRole.ActionRole)
            btn_report.clicked.disconnect()
            btn_report.clicked.connect(self._cb_report_bug)
        else:
            btn_copy = self._dialog.addButton(_tr('Copy traceback...'),
                                              QMessageBox.ButtonRole.ActionRole)
            btn_copy.clicked.disconnect()
            btn_copy.clicked.connect(self._cb_copy_to_clipboard)

            secondary += _tr('\n\nPlease remember to include the '
                             'traceback from the Details expander.')

        self._dialog.setInformativeText(secondary)

        # Workaround for the X button not working when details are available
        # Source: https://stackoverflow.com/a/32764190/435253
        btn_close = self._dialog.addButton(QMessageBox.StandardButton.Close)
        self._dialog.setEscapeButton(btn_close)

        self.b_quit = self._dialog.addButton(_tr('Quit'), QMessageBox.ButtonRole.RejectRole)


    def _cb_copy_to_clipboard(self):
        """Qt slot for the :guilabel:`Copy traceback...` button."""
        QApplication.instance().clipboard().setText(
            self._dialog.detailedText())

        QMessageBox(QMessageBox.Icon.Information,
            _tr('Traceback Copied'),
            _tr('The traceback has now been copied to the clipboard.')
                    ).exec_()

    @Slot()
    def _cb_report_bug(self):
        """Qt slot for the :guilabel:`Report bug...` button. """
        self._reporting_cb(self._dialog.detailedText())

    def set_recovery(self, recovery_cb: Optional[Callable[[], bool]],
                     recovery_enabled_cb: Optional[Callable[[], bool]] = None) -> None:
        """Sets the Quit button's recovery callbacks, for hooks enabled before the recovery source exists."""
        self._recovery_cb = recovery_cb
        self._recovery_enabled_cb = recovery_enabled_cb

    def _excepthook(self, exc_type, exc_value, exc_traceback):
        """Replacement system exception handler callback. Runs on whichever thread raised the exception."""
        # Always reach the log and the console: Qt prints only "Error calling Python override of ..." for exceptions
        # raised in virtual overrides such as QStyle.styleHint.
        logger.error('Uncaught exception', exc_info=(exc_type, exc_value, exc_traceback))
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

        # Qt UI actions outside the main thread cause segfaults, so the dialog is queued there.
        if threading.current_thread() is not threading.main_thread():
            run_on_main_thread(lambda: self._show_dialog(exc_type, exc_value, exc_traceback))
            return
        self._show_dialog(exc_type, exc_value, exc_traceback)

    def _report_text(self, exc_type: type[BaseException], exc_value: BaseException,
                     exc_traceback: Optional[TracebackType]) -> str:
        """Returns the bug report text: a plain traceback (no local variables) and the environment details."""
        traceback_text = ''.join(traceback.TracebackException(exc_type, exc_value, exc_traceback).format())
        extra_info = ''
        if self._extra_info_cb is not None:
            try:
                extra_info = self._extra_info_cb()
            except Exception as err:  # pylint: disable=broad-exception-caught
                extra_info = f'Failed to read environment details: {err}'
        if extra_info:
            traceback_text += f'\n{extra_info}'
        return traceback_text

    def _show_dialog(self, exc_type, exc_value, exc_traceback) -> None:
        """Shows the dialog for an exception that was already logged. Main thread only."""
        # Showing the dialog runs style and paint callbacks. If one of them raises, it re-enters this hook while
        # the dialog is open, and a nested exec() call fails with "Recursive call detected", so the first dialog's
        # details are kept and the repeat is only logged.
        if self._showing:
            return

        traceback_text = self._report_text(exc_type, exc_value, exc_traceback)

        # Store it in the dialog where everything retrieves it from
        self._dialog.setDetailedText(traceback_text)

        if self._recovery_cb is not None:
            recoverable = self._recovery_enabled_cb is None or self._recovery_enabled_cb()
            self.b_quit.setText(_tr('Quit (your work can be recovered next launch)') if recoverable
                                else _tr('Quit (unsaved changes will be lost)'))

        # Show the dialog
        self._showing = True
        try:
            self._dialog.exec()
        finally:
            self._showing = False
        if self._dialog.clickedButton() == self.b_quit:
            if self._recovery_cb is not None:
                try:
                    self._recovery_cb()
                except Exception as err:  # pylint: disable=broad-exception-caught
                    print(f'Failed to keep the recovery copy: {err}', file=sys.stderr)
            QApplication.instance().quit()

    def enable(self):
        """Replace the default exception handler with this one"""
        sys.excepthook = self._excepthook
