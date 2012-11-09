import cv

def match(_original, template, scale_template=1):

    original = cv.CloneImage(_original)

    scaled_template = cv.CreateImage((int(template.width*scale_template),
        int(template.height*scale_template)),
        template.depth, 3)
    cv.Resize(template, scaled_template)

    res_height = original.height - scaled_template.height + 1
    res_width = original.width - scaled_template.width + 1
    if res_height < 0 or res_width < 0:
        return (-1, -1, -1)

    resimg = cv.CreateImage((res_width, res_height), cv.IPL_DEPTH_32F, 1)
    cv.Zero(resimg)
    cv.MatchTemplate(original, scaled_template, resimg, cv.CV_TM_CCOEFF_NORMED)

    minval, maxval, minloc, maxloc = cv.MinMaxLoc(resimg)

    if maxval >= .7:
        cv.Rectangle(original, maxloc,
            (maxloc[0] + scaled_template.width, maxloc[1] + scaled_template.height),
            cv.RGB(255, 0, 0), 2, 8, 0)

    #cv.ShowImage('proc', original)
    #import time
    #time.sleep(0.5)
    #cv.WaitKey(1000)

    return (maxval, maxloc[0] + int(scaled_template.width / 2),
                    maxloc[1] + int(scaled_template.height / 2))
