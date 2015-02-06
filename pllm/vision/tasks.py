import os
from operator import itemgetter

import cv2

from pllm import config, util

from pllm.vision import algo
from pllm.vision.util import draw_segments, split_fpath
from pllm.vision.ocr import ocr


def ocr_full(fpath):
    txt = ocr(fpath, block=False)
    return txt


def ocr_segments(fpath):
    segs = segmentize(fpath)
    segs_res = {}

    for segname, shape in segs.items():
        x, y, w, h = shape
        seg_ocr = ocr(segname)
        if seg_ocr:
            segs_res[segname] = (shape, seg_ocr)


    return segs_res


def segmentize(fpath):
    """
    Read `fpath` image, find its segments
    and store as separate images.
    """

    fdir, fname = split_fpath(fpath)

    img = cv2.imread(fpath)
    vis = img.copy()

    segments = algo.mser_segments(img)

    vis = img.copy()
    vis = draw_segments(vis, segments)
    cv2.imwrite("{0}/mser.png".format(fdir), vis)

    kmeans_img = algo.kmeans_quantize(img)
    cv2.imwrite("{0}/kmeans.png".format(fdir), kmeans_img)

    for inv in [True, False]:
        contour_segments = algo.contour_segments(kmeans_img, invert=inv)
        vis = img.copy()
        vis = draw_segments(vis, contour_segments)

        invn = ''
        if inv:
            invn = '_inv'

        cv2.imwrite("{0}/csegs{1}.png".format(fdir, invn), vis)
        segments.extend(contour_segments)

    segments = segment_filter(segments)
    vis = img.copy()
    vis = draw_segments(vis, segments)
    cv2.imwrite("{0}/filtered_segments.png".format(fdir), vis)

    merged_segments = add_merged_close_segments(segments)

    if merged_segments:
        vis = img.copy()
        vis = draw_segments(vis, merged_segments)
        cv2.imwrite("{0}/merged_segments.png".format(fdir), vis)

        segments.extend(merged_segments)

    segs = {}

    # save found segments
    for (x, y, w, h) in segments:
        roi = img[y:y + h, x:x + w]
        segname = "{0}/{1}_segment_{2}_{3}.png".format(fdir, fname, x, y)
        cv2.imwrite(segname, roi)
        segs[segname] = (x, y, w, h)

    return segs


def segment_filter(segments):
    nsegs = []
    for seg in segments:
        x, y, w, h = seg
        if w < 30 or h < 10:  # too small
            continue

        if h > 60:  # we do not really benefit from multiline segments
            continue

        nsegs.append(seg)

    return nsegs


def add_merged_close_segments(segments,
                              near_x=10,
                              near_y=10,
                              grow=2):

    dbg_segments = False

    nsegs = []
    segs_len = len(segments)
    y_sorted = sorted(segments, key=itemgetter(1))

    for i, seg in enumerate(y_sorted):
        x, y, w, h = seg
        low = i - 1

        while low >= 0:
            ny = y_sorted[low][1]
            if y - ny > near_y:
                if dbg_segments:
                    print(y_sorted[low], low, "is too far low by ", y - ny)
                break

            if dbg_segments:
                print(y_sorted[low], low, "is near low by ", y - ny)
            low -= 1

        high = i + 1

        while high < segs_len:
            ny = y_sorted[high][1]
            if ny - y > near_y:
                if dbg_segments:
                    print(y_sorted[high], high, "is too far highigh by ", ny - y)
                break

            if dbg_segments:
                print(y_sorted[high], high, "is near highigh by ", ny - y)
            high += 1

        if low == i - 1 and high == i + 1:  # no change
            continue

        if dbg_segments:
            print(seg, "Candidates", y_sorted[low + 1:high])

        for candidate in sorted(y_sorted[low + 1:high]):
            cx, cy, cw, ch = candidate
            if candidate == seg:
                continue

            xw = x + w  # right edge
            if abs(xw - cx) < near_x:
                if dbg_segments:
                    print(candidate, "edge near x", xw - cx)
                new_x = min(x, cx) - grow
                new_y = min(y, cy) - grow
                new_w = (max(x + w, cx + cw) - new_x) + grow
                new_h = (max(y + h, cy + ch) - new_y) + grow
                new = (new_x, new_y, new_w, new_h)
                nsegs.append(new)

    if dbg_segments:
        print("found", len(nsegs), nsegs)

    return nsegs


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

        cv2.imwrite("{0}/match_{1}.png".format(fdir, template_name),
                    target)

    return (max_val >= threshold, x, y)
