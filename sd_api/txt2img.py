from sd_api.endpoint import Endpoint

class Txt2ImgPost(Endpoint):
    def __init__(self, url):
        super().__init__(url, '/sdapi/v1/txt2img', 'POST')

    def _createBody(self, config, width, height):
        return {
            'prompt': config.get('prompt'),
            'seed': config.get('seed'),
            'batch_size': config.get('batchSize'),
            'n_iter': config.get('batchCount'),
            'steps': config.get('samplingSteps'),
            'cfg_scale': config.get('cfgScale'),
            'width': width,
            'height': height,
            'restore_faces': config.get('restoreFaces'),
            'tiling': config.get('tiling'),
            'negative_prompt': config.get('negativePrompt'),
            'override_settings': {},
            'sampler_index': config.get('samplingMethod')
        }

