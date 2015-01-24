import os

import cv
import cv2
import tesseract
from twisted.python import log

import algo

from pllm import config, util


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
    # adaptive
    #thr = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    #                            cv2.THRESH_BINARY, 11, 2)
    optname = "{0}/{1}_ocropt.png".format(fdir, name)

    cv2.imwrite(optname, res)
    return optname


def segmentize(fpath):
    """
    Read `fpath` image, find its segments
    and store as separate images.
    """

    fdir, fname = os.path.split(fpath)
    name = fname[:fname.rfind('.')]  # ext is .png

    img = cv2.imread(fpath)
    vis = img.copy()

    segments = algo.mser_segments(img)

    vis = img.copy()
    segs = {}

    # save found segments
    for (x, y, w, h) in segments:
        cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 255, 0), 1)

        roi = img[y:y + h, x:x + w]
        segname = "{0}/{1}_segment_{2}_{3}.png".format(fdir, name, x, y)
        cv2.imwrite(segname, roi)
        opt = ocr_optimize(segname)
        segs[opt] = (x, y, w, h)

    cv2.imwrite("{0}/{1}_mser.png".format(fdir, name), vis)

    return segs


def process(fpath):
    opt_fpath = ocr_optimize(fpath)

    full = ocr(opt_fpath, block=False)

    segs = segmentize(fpath)
    segs_res = {}

    for segname, shape in segs.items():
        x, y, w, h = shape
        seg_ocr = ocr(segname)
        if seg_ocr:
            segs_res[segname] = (shape, seg_ocr)

    return (full, segs_res)


def template_match(target_fpath, template_name):
    """
    Match template_name image against target_fpath

    Returns (match_succes:bool, x:int, y:int)

    x, y pointing to center of the matched region
    """

    target = cv2.imread(target_fpath)
    template = cv2.imread(util.template_path(template_name))
    h, w, d = template.shape

    fdir, fname = os.path.split(target_fpath)
    #name = fname[:fname.rfind('.')]  # ext is .png

    max_val, x, y = algo.template_match(target, template)

    scale_template = 1  # unused for now
    if scale_template != 1:
        template = cv2.resize(template, None,
                              fx=scale_template,
                              fy=scale_template,
                              interpolation=cv2.INTER_CUBIC)

    threshold = config.get('treshold')
    if max_val >= threshold:
        cv2.rectangle(target, (x - w / 2, y - h / 2), (x + w / 2, y + h / 2),
                      (0, 255, 0), 1)

        cv2.imwrite("{0}/{1}_template_match.png".format(fdir, template_name),
                    target)

    return (max_val >= threshold, x, y)
