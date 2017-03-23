from imagekit import ImageSpec, register
from imagekit.processors import ResizeToFill

class ExplicitCrop(object):

    def __init__(self, top, right, bottom, left):
        self.top = top
        self.right = right
        self.bottom = bottom
        self.left = left

    def process(self, img):
        (w, h) = img.size
        return img.crop((self.left, self.top, w - self.right, h - self.bottom))

class StatementPageHeadshot(ImageSpec):
    processors = [ExplicitCrop(10, 10, 68, 10), # should give us 122x152
        ResizeToFill(100, 125)]
    format = 'JPEG'
    options = {'quality': 80}


register.generator('op:statement_headshot', StatementPageHeadshot)
