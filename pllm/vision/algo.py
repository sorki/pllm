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


def adaptive_optimize(img, upscale=5, threshold=200, blur=1):
    """
    Optimize image for further OCR processing

    - upscale
    - convert to gray
    - blur
    - adaptive threshold
    """

    img = cv2.resize(img, None, fx=upscale, fy=upscale,
                     interpolation=cv2.INTER_CUBIC)

    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img = cv2.medianBlur(img, blur)
    img = cv2.adaptiveThreshold(img, threshold,
                                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 11, 2)

    return img


def sobel_optimize(img, upscale=5, median_blur=1, color_offset=200):
    """
    Optimize image for OCR processing using Sobel operator

    Unused for now
    """

    img = cv2.resize(img, None, fx=upscale, fy=upscale,
                     interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    ddepth = cv2.CV_16S
    delta = 0
    scale = 1

    grad_x = cv2.Sobel(gray, ddepth, 1, 0, ksize=3,
                       scale=scale, delta=delta, borderType=cv2.BORDER_DEFAULT)
    grad_y = cv2.Sobel(gray, ddepth, 0, 1, ksize=3,
                       scale=scale, delta=delta, borderType=cv2.BORDER_DEFAULT)

    abs_grad_x = cv2.convertScaleAbs(grad_x)
    abs_grad_y = cv2.convertScaleAbs(grad_y)
    im = cv2.addWeighted(abs_grad_x, 0.5, abs_grad_y, 0.5, 0)

    im = cv2.medianBlur(gray, median_blur)
    im[im >= color_offset] = 255
    im[im < color_offset] = 0  # black

    return im


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


def contours(im, bounding_box_x_adjust=4):
    """
    Find contours and their bounding boxes

    Returns list of found segments
    """

    cim = im.copy()  # findContours alters src image
    contours, hierarchy = cv2.findContours(
        cim, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    segs = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        y -= bounding_box_x_adjust
        y = max(1, y)
        segs.append((x, y, w, h))

    return segs


def contour_segments(im, invert=True, threshold=130,
                     erode_iters=1, erode_k1_size=2, erode_k2_size=2,
                     dilate_iters=5, dilate_k1_size=5, dilate_k2_size=2,
                     bounding_box_x_adjust=4):
    """
    Pre-process image using erosion/dilation and find
    segments resembling text lines using contour search
    """

    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    ret, im = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

    if invert:
        im = cv2.bitwise_not(im)

    im = erode(im, erode_iters, erode_k1_size, erode_k2_size)
    im = dilate(im, dilate_iters, dilate_k1_size, dilate_k2_size)
    return contours(im)
