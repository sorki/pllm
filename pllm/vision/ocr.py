import os
import subprocess

import cv
import cv2

from pllm.vision import algo


try:
    import tesseract
    ts_native_available = True
except ImportError:
    ts_native_available = False


def tesseract_native(fpath, lang, block=True):
    """
    Use tesseract Python API to process `fpath`
    pre-segmented image
    """

    api = tesseract.TessBaseAPI()
    api.Init(".", lang, tesseract.OEM_DEFAULT)
    if block:
        api.SetPageSegMode(tesseract.PSM_SINGLE_BLOCK)
    else:
        api.SetPageSegMode(tesseract.PSM_AUTO)

    img = cv.LoadImage(fpath, iscolor=False)
    tesseract.SetCvImage(img, api)
    text = api.GetUTF8Text()
    return text


def tesseract_fork(fpath, lang, block=True):
    """
    Use tesseract command line interface
    to process `fpath` pre-segmented image

    Fallback version of tesseract_native
    when Python bindings are not available.
    Slower as it is forking.
    """

    # tesseract --help
    psm = 1  # auto
    if block:
        psm = 3  # single block

    # tesseract <in_file> stdout -l <lang> -psm <psm>
    cmd = ["/usr/bin/tesseract", fpath, "stdout", "-l",
           lang, "-psm", str(psm)]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            close_fds=True)

    (stdout, stderr) = proc.communicate()
    return stdout


def ocr(fpath, block=True):
    """
    Recognize text in image specified by `fpath`.
    Should contain single block of text (pre-segmented)
    """

    if ts_native_available:
        fn = tesseract_native
    else:
        fn = tesseract_fork

    lang = "eng"
    txt = fn(fpath, lang, block)

    return txt


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
