import cv2


def draw_segments(im, segments):
    """
    Visualize segments found by MSER/contours algorithms
    """

    for (x, y, w, h) in segments:
        cv2.rectangle(im, (x, y), (x + w, y + h), (0, 255, 0), 1)

    return im
