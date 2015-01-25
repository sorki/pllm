import cv2
import numpy as np

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


def kmeans_quantize(img, clusters=2):
    """
    Color quantization into number of clusters
    """

    Z = img.reshape((-1, 3))
    Z = np.float32(Z)

    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 10, 1)
    ret, label, center = cv2.kmeans(
        Z, clusters, criteria, 1, flags=cv2.KMEANS_RANDOM_CENTERS)

    center = np.uint8(center)
    res = center[label.flatten()]
    return res.reshape((img.shape))


def erode(im, iters=1, k1_size=2, k2_size=2):
    """
    Erode image
    """

    elem_type = cv2.MORPH_RECT
    k = cv2.getStructuringElement(elem_type, (k1_size, k2_size))
    return cv2.erode(im, k, iterations=iters)


def dilate(im, iters=5, k1_size=5, k2_size=2):
    """
    Dilate image
    """

    elem_type = cv2.MORPH_RECT
    k = cv2.getStructuringElement(elem_type, (k1_size, k2_size))
    return cv2.dilate(im, k, iterations=iters)


def contour_segments(im, bounding_box_x_adjust=4):
    """
    Segmentize image using contour search
    """

    cim = im.copy()  # findContours alters src image
    contours, hierarchy = cv2.findContours(
        cim, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    segs = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        y -= bounding_box_x_adjust
        segs.append((x, y, w, h))

    return segs
