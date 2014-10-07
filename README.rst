pllm
----

Phase locked loop method? No.

GUI testing framework aiming for robustness and ease of use.

This project is inspired by `Sikuli <http://sikuli.org>`_ and `os-autoinst <http://os-autoinst.org>`_ projects aiming
to get the best of these projects to provide next-generation
GUI testing tool for general audience.

Technologies used
=================

- `Python <http://python.org>`_
- `Twisted <http://twistedmatrix.com>`_
- `libvirt <http://libvirt.org>`_
- `OpenCV <http://opencv.willowgarage.com>`_
- `tesseract-ocr <http://code.google.com/p/tesseract-ocr/>`_
- VNC

Prototype description
======================


Pllm is able to automatically perform a set of actions
against a running virtual machine. These include:
- template matching
- text recognition
- interaction based on results of previous two methods

DSL or call it an API is provided for writing the tests. This consists of
Python code with number of convenience functions to handle common tasks like
waiting for a template to appear, clicking on it or branching which depends
on matched template (expect).

Tests are then interpreted within a debugger which allows for runtime observation
and manipulation of currently executed test.
