# Translating IntraPaint

If anyone feels like translating IntraPaint, I'd love to add your translations to the project. Here's what you need to do to add a translation:

1. Install Qt Linguist. Download links and the program manual can be found here: https://doc.qt.io/qt-6/linguist-translators.html
2. Create a copy of main.ts. Name it after the country/language code you intend to add(e.g. "ex-MX.ts" for Spanish - Mexico).
3. Open it in Qt Linguist. In the edit menu, go to "translation file settings", and change the "Language" and "Country/Region" dropdowns under the Target language section to your region and language.
4. Go through all the entries in the file, and add translations.
5. Save the file, and also select "Release" in the File menu to create a final .qm file.
6. Create a pull release to add the new .ts and .qm files to the project, or just send the files to me. I'll test them and merge them into the main codebase.