import os

import cv
import cv2
import tesseract

from pllm.vision import algo


def ocr(fpath, block=True):
    """
    Recognize text in image specified by `fpath`.
    Should contain single block of text (pre-segmented)
    """

    api = tesseract.TessBaseAPI()
    api.Init(".", "eng", tesseract.OEM_DEFAULT)
    if block:
        api.SetPageSegMode(tesseract.PSM_SINGLE_BLOCK)
    else:
        api.SetPageSegMode(tesseract.PSM_AUTO)

    img = cv.LoadImage(fpath, iscolor=False)
    tesseract.SetCvImage(img, api)
    text = api.GetUTF8Text()
    return text


def ocr_optimize(fpath, upscale=5, threshold=160):
    """
    Optimize `fpath` image for ocr
    """

    fdir, fname = os.path.split(fpath)
    name = fname[:fname.rfind('.')]  # ext is .png

    img = cv2.imread(fpath)
    res = algo.ocr_optimize(img)

    optname = "{0}/{1}_ocropt.png".format(fdir, name)

    cv2.imwrite(optname, res)
    return optname
