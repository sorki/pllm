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

tesseract_opts = {
    'tessedit_char_whitelist': ('0123456789'
    + 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    + ',.:*!?-=/'),
    'language_model_penalty_non_freq_dict_word': '0.5',
    'language_model_penalty_non_dict_word': '0.25',
}


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

    for opt, val in tesseract_opts.items():
        api.SetVariable(opt, val)

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

    for opt, val in tesseract_opts.items():
        cmd.append("-c")
        cmd.append("{0}={1}".format(opt, val))

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            close_fds=True)

    (stdout, stderr) = proc.communicate()
    return stdout


def ocr(fpath, block=True):
    """
    Optimize & ocr fpath
    """

    result = ""
    for opt_fpath in ocr_optimize(fpath):
        res = ocr_single(opt_fpath, block)

        if not res:
            continue

        if res in result:  # already got this
            continue

        result += " {0}".format(res)

    return result.strip()


def ocr_single(fpath, block=True):
    """
    Recognize text in image specified by `fpath`.
    Should contain single block of text (pre-segmented)
    """

    fdir, fname = os.path.split(fpath)
    name = fname[:fname.rfind('.')]  # ext is .png

    if ts_native_available:
        fn = tesseract_native
    else:
        fn = tesseract_fork

    lang = "eng"
    txt = fn(fpath, lang, block)

    fname_txt = "{0}/{1}.txt".format(fdir, name)
    with open(fname_txt, "w") as ftxt:
        ftxt.write(txt)

    return txt


OPTIMIZE_ALGO = ["ocr_optimize"]


def ocr_optimize(fpath):
    """
    Optimize `fpath` image for ocr
    """

    fdir, fname = os.path.split(fpath)
    name = fname[:fname.rfind('.')]  # ext is .png

    img = cv2.imread(fpath)

    results = []

    for algo_name in OPTIMIZE_ALGO:
        fn = getattr(algo, algo_name)

        res = fn(img)

        optname = "{0}/{1}_{2}.png".format(fdir, name, algo_name)

        cv2.imwrite(optname, res)

        results.append(optname)

    return results
