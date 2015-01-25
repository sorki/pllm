import os

import cv2

from pllm import config, util
from pllm.vision import algo
from pllm.vision.util import draw_segments
from pllm.vision.ocr import ocr, ocr_optimize


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
    vis = draw_segments(vis, segments)
    cv2.imwrite("{0}/{1}_mser.png".format(fdir, name), vis)

    segs = {}

    # save found segments
    for (x, y, w, h) in segments:
        roi = img[y:y + h, x:x + w]
        segname = "{0}/{1}_segment_{2}_{3}.png".format(fdir, name, x, y)
        cv2.imwrite(segname, roi)
        opt = ocr_optimize(segname)
        segs[opt] = (x, y, w, h)

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
