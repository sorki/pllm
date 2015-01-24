import cv2


# segs result: [(x, y, w, h), ..]

def mser_segments(img, delta=3,
                  min_area=500, max_area=35000,
                  max_variation=0.1, min_diversity=0.5):
    """
    Find image segments using MSER (Maximally stable extremal regions)
    algorithm.

    Returns list of (x, y, w, h) tuples of detected segments.
    """

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    mser = cv2.MSER(delta, min_area, max_area, max_variation,
                    min_diversity)

    regions = mser.detect(gray)

    hulls = [cv2.convexHull(p.reshape(-1, 1, 2)) for p in regions]

    segs = []
    for s in hulls:
        x, y, w, h = cv2.boundingRect(s)
        segs.append((x, y, w, h))

    return segs


def template_match(target, template):
    """
    Match template against target
    """

    h, w, d = template.shape

    res = cv2.matchTemplate(target, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    return max_val, max_loc[0] + w / 2, max_loc[1] + h / 2


def ocr_optimize(img, upscale=5, threshold=160, blur_kernel_size=4):
    """
    Optimize image for further OCR processing

    - upscale
    - convert to gray
    - blur
    - threshold
    """

    img = cv2.resize(img, None, fx=upscale, fy=upscale,
                     interpolation=cv2.INTER_CUBIC)

    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img = cv2.blur(img, (blur_kernel_size, blur_kernel_size))
    ret, img = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY)

    return img
