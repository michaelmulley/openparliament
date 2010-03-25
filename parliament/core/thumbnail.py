
import pdb

def crop_first(image, requested_size, opts):
    if 'crop_first' in opts:
        (t, r, b, l) = (int(x) for x in opts['crop_first'].split(','))
        (w, h) = image.size
        image = image.crop((l, t, w-r, h-b))
    return image
crop_first.valid_options = ['crop_first']