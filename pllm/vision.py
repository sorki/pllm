import os

import cv
import cv2
import tesseract
from twisted.python import log


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
    img = cv2.resize(img, None, fx=upscale, fy=upscale,
                     interpolation=cv2.INTER_CUBIC)

    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img = cv2.blur(img, (4, 4))
    ret, thr = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY)

    # adaptive
    #thr = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    #                            cv2.THRESH_BINARY, 11, 2)
    optname = "{0}/{1}_ocropt.png".format(fdir, name)

    cv2.imwrite(optname, thr)
    return optname


def segmentize(fpath):
    """
    Read `fpath` image, find its segments
    and store as separate images.
    """

    fdir, fname = os.path.split(fpath)
    name = fname[:fname.rfind('.')]  # ext is .png

    img = cv2.imread(fpath)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    vis = img.copy()

    delta = 3
    min_area = 500
    max_area = 35000
    max_variation = 0.10
    min_diversity = 0.50

    mser = cv2.MSER(delta, min_area, max_area, max_variation,
                    min_diversity)

    regions = mser.detect(gray, None)

    hulls = [cv2.convexHull(p.reshape(-1, 1, 2)) for p in regions]

    # visualize what mser found
    cv2.polylines(vis, hulls, 1, (0, 255, 0))
    cv2.imwrite("{0}/{1}_mser.png".format(fdir, name), vis)

    vis = img.copy()
    segs = {}

    # save found segments
    for s in hulls:
        x, y, w, h = cv2.boundingRect(s)
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


def template_match(target, template):
    h, w, d = template.shape

    res = cv2.matchTemplate(target, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    return max_val, max_loc[0] + w / 2, max_loc[1] + h / 2


def template_match_paths(target_fpath, template_fpath,
                         scale_template=1, threshold=0.9):

    target = cv2.imread(target_fpath)
    template = cv2.imread(template_fpath)
    h, w, d = template.shape

    fdir, fname = os.path.split(target_fpath)
    name = fname[:fname.rfind('.')]  # ext is .png

    max_val, x, y = template_match(target, template)

    if scale_template != 1:
        template = cv2.resize(template, None,
                              fx=scale_template,
                              fy=scale_template,
                              interpolation=cv2.INTER_CUBIC)

    if max_val >= threshold:
        log.msg("Template matched, max_val: {0:.2}".format(max_val))

        cv2.rectangle(target, (x - w / 2, y - h / 2), (x + w / 2, y + h / 2),
                      (255, 0, 0), 2)

        cv2.imwrite("{0}/{1}_template_match.png".format(fdir, name), target)

    return (max_val, x, y)


if __name__ == "__main__":
    res = template_match_paths("/tmp/pllm/run/last.png",
                               "../img/anaconda_done_btn.png")

    print res
    import sys
    sys.exit(0)

    full, segs_res = process("/tmp/pllm/test/welcome.png")
    #full, segs_res = process("/tmp/pllm/test/dialog.png")
    #full, segs_res = process("/tmp/pllm/run/1.png")
    full, segs_res = process("/tmp/pllm/run/last.png")

    print("Full: {0}".format(full))
    for segname, (shape, txt) in segs_res.items():
        x, y, w, h = shape
        print("{0}x{1}".format(x, y))
        print(txt)
