import shutil
import tempfile
import unittest

import pytest

from myTransformers import Owlv2Processor
from myTransformers.testing_utils import require_scipy

from ...test_processing_common import ProcessorTesterMixin


@require_scipy
class Owlv2ProcessorTest(ProcessorTesterMixin, unittest.TestCase):
    processor_class = Owlv2Processor

    @classmethod
    def setUpClass(cls):
        cls.tmpdirname = tempfile.mkdtemp()
        processor = cls.processor_class.from_pretrained("google/owlv2-base-patch16-ensemble")
        processor.save_pretrained(cls.tmpdirname)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdirname, ignore_errors=True)

    def test_processor_query_images_positional(self):
        processor_components = self.prepare_components()
        processor = Owlv2Processor(**processor_components)

        image_input = self.prepare_image_inputs()
        query_images = self.prepare_image_inputs()

        inputs = processor(None, image_input, query_images)

        self.assertListEqual(list(inputs.keys()), ["query_pixel_values", "pixel_values"])

        # test if it raises when no input is passed
        with pytest.raises(ValueError):
            processor()
