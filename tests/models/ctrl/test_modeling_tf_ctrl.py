# Copyright 2020 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from __future__ import annotations

import unittest

from myTransformers import CTRLConfig, is_tf_available
from myTransformers.testing_utils import require_tf, slow

from ...test_configuration_common import ConfigTester
from ...test_modeling_tf_common import TFModelTesterMixin, ids_tensor, random_attention_mask
from ...test_pipeline_mixin import PipelineTesterMixin


if is_tf_available():
    import tensorflow as tf

    from myTransformers.modeling_tf_utils import keras
    from myTransformers.models.ctrl.modeling_tf_ctrl import (
        TFCTRLForSequenceClassification,
        TFCTRLLMHeadModel,
        TFCTRLModel,
    )


class TFCTRLModelTester:
    def __init__(
        self,
        parent,
    ):
        self.parent = parent
        self.batch_size = 13
        self.seq_length = 7
        self.is_training = True
        self.use_token_type_ids = True
        self.use_input_mask = True
        self.use_labels = True
        self.use_mc_token_ids = True
        self.vocab_size = 99
        self.hidden_size = 32
        self.num_hidden_layers = 2
        self.num_attention_heads = 4
        self.intermediate_size = 37
        self.hidden_act = "gelu"
        self.hidden_dropout_prob = 0.1
        self.attention_probs_dropout_prob = 0.1
        self.max_position_embeddings = 512
        self.type_vocab_size = 16
        self.type_sequence_label_size = 2
        self.initializer_range = 0.02
        self.num_labels = 3
        self.num_choices = 4
        self.scope = None
        self.pad_token_id = self.vocab_size - 1

    def prepare_config_and_inputs(self):
        input_ids = ids_tensor([self.batch_size, self.seq_length], self.vocab_size)

        input_mask = None
        if self.use_input_mask:
            input_mask = random_attention_mask([self.batch_size, self.seq_length])

        token_type_ids = None
        if self.use_token_type_ids:
            token_type_ids = ids_tensor([self.batch_size, self.seq_length], self.type_vocab_size)

        mc_token_ids = None
        if self.use_mc_token_ids:
            mc_token_ids = ids_tensor([self.batch_size, self.num_choices], self.seq_length)

        sequence_labels = None
        token_labels = None
        choice_labels = None
        if self.use_labels:
            sequence_labels = ids_tensor([self.batch_size], self.type_sequence_label_size)
            token_labels = ids_tensor([self.batch_size, self.seq_length], self.num_labels)
            choice_labels = ids_tensor([self.batch_size], self.num_choices)

        config = CTRLConfig(
            vocab_size=self.vocab_size,
            n_embd=self.hidden_size,
            n_layer=self.num_hidden_layers,
            n_head=self.num_attention_heads,
            dff=self.intermediate_size,
            # hidden_act=self.hidden_act,
            # hidden_dropout_prob=self.hidden_dropout_prob,
            # attention_probs_dropout_prob=self.attention_probs_dropout_prob,
            n_positions=self.max_position_embeddings,
            # type_vocab_size=self.type_vocab_size,
            # initializer_range=self.initializer_range,
            pad_token_id=self.pad_token_id,
        )

        head_mask = ids_tensor([self.num_hidden_layers, self.num_attention_heads], 2)

        return (
            config,
            input_ids,
            input_mask,
            head_mask,
            token_type_ids,
            mc_token_ids,
            sequence_labels,
            token_labels,
            choice_labels,
        )

    def create_and_check_ctrl_model(self, config, input_ids, input_mask, head_mask, token_type_ids, *args):
        model = TFCTRLModel(config=config)
        inputs = {"input_ids": input_ids, "attention_mask": input_mask, "token_type_ids": token_type_ids}
        result = model(inputs)

        inputs = [input_ids, None, input_mask]  # None is the input for 'past'
        result = model(inputs)

        result = model(input_ids)

        self.parent.assertEqual(result.last_hidden_state.shape, (self.batch_size, self.seq_length, self.hidden_size))

    def create_and_check_ctrl_lm_head(self, config, input_ids, input_mask, head_mask, token_type_ids, *args):
        model = TFCTRLLMHeadModel(config=config)
        inputs = {"input_ids": input_ids, "attention_mask": input_mask, "token_type_ids": token_type_ids}
        result = model(inputs)
        self.parent.assertEqual(result.logits.shape, (self.batch_size, self.seq_length, self.vocab_size))

    def create_and_check_ctrl_for_sequence_classification(
        self, config, input_ids, input_mask, head_mask, token_type_ids, *args
    ):
        config.num_labels = self.num_labels
        sequence_labels = ids_tensor([self.batch_size], self.type_sequence_label_size)
        inputs = {
            "input_ids": input_ids,
            "token_type_ids": token_type_ids,
            "labels": sequence_labels,
        }
        model = TFCTRLForSequenceClassification(config)
        result = model(inputs)
        self.parent.assertEqual(result.logits.shape, (self.batch_size, self.num_labels))

    def prepare_config_and_inputs_for_common(self):
        config_and_inputs = self.prepare_config_and_inputs()

        (
            config,
            input_ids,
            input_mask,
            head_mask,
            token_type_ids,
            mc_token_ids,
            sequence_labels,
            token_labels,
            choice_labels,
        ) = config_and_inputs

        inputs_dict = {"input_ids": input_ids, "token_type_ids": token_type_ids, "attention_mask": input_mask}
        return config, inputs_dict


@require_tf
class TFCTRLModelTest(TFModelTesterMixin, PipelineTesterMixin, unittest.TestCase):
    all_model_classes = (TFCTRLModel, TFCTRLLMHeadModel, TFCTRLForSequenceClassification) if is_tf_available() else ()
    all_generative_model_classes = (TFCTRLLMHeadModel,) if is_tf_available() else ()
    pipeline_model_mapping = (
        {
            "feature-extraction": TFCTRLModel,
            "text-classification": TFCTRLForSequenceClassification,
            "text-generation": TFCTRLLMHeadModel,
            "zero-shot": TFCTRLForSequenceClassification,
        }
        if is_tf_available()
        else {}
    )
    test_head_masking = False
    test_onnx = False

    # TODO: Fix the failed tests
    def is_pipeline_test_to_skip(
        self,
        pipeline_test_case_name,
        config_class,
        model_architecture,
        tokenizer_name,
        image_processor_name,
        feature_extractor_name,
        processor_name,
    ):
        if pipeline_test_case_name == "ZeroShotClassificationPipelineTests":
            # Get `tokenizer does not have a padding token` error for both fast/slow tokenizers.
            # `CTRLConfig` was never used in pipeline tests, either because of a missing checkpoint or because a tiny
            # config could not be created.
            return True

        return False

    def setUp(self):
        self.model_tester = TFCTRLModelTester(self)
        self.config_tester = ConfigTester(self, config_class=CTRLConfig, n_embd=37)

    def test_config(self):
        self.config_tester.run_common_tests()

    def test_ctrl_model(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        self.model_tester.create_and_check_ctrl_model(*config_and_inputs)

    def test_ctrl_lm_head(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        self.model_tester.create_and_check_ctrl_lm_head(*config_and_inputs)

    def test_ctrl_sequence_classification_model(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        self.model_tester.create_and_check_ctrl_for_sequence_classification(*config_and_inputs)

    def test_model_common_attributes(self):
        config, inputs_dict = self.model_tester.prepare_config_and_inputs_for_common()
        list_lm_models = [TFCTRLLMHeadModel]
        list_other_models_with_output_ebd = [TFCTRLForSequenceClassification]

        for model_class in self.all_model_classes:
            model = model_class(config)
            model.build_in_name_scope()  # may be needed for the get_bias() call below
            assert isinstance(model.get_input_embeddings(), keras.layers.Layer)

            if model_class in list_lm_models:
                x = model.get_output_embeddings()
                assert isinstance(x, keras.layers.Layer)
                name = model.get_bias()
                assert isinstance(name, dict)
                for k, v in name.items():
                    assert isinstance(v, tf.Variable)
            elif model_class in list_other_models_with_output_ebd:
                x = model.get_output_embeddings()
                assert isinstance(x, keras.layers.Layer)
                name = model.get_bias()
                assert name is None
            else:
                x = model.get_output_embeddings()
                assert x is None
                name = model.get_bias()
                assert name is None

    @slow
    def test_model_from_pretrained(self):
        model_name = "Salesforce/ctrl"
        model = TFCTRLModel.from_pretrained(model_name)
        self.assertIsNotNone(model)


@require_tf
class TFCTRLModelLanguageGenerationTest(unittest.TestCase):
    @slow
    def test_lm_generate_ctrl(self):
        model = TFCTRLLMHeadModel.from_pretrained("Salesforce/ctrl")
        input_ids = tf.convert_to_tensor([[11859, 0, 1611, 8]], dtype=tf.int32)  # Legal the president is
        expected_output_ids = [
            11859,
            0,
            1611,
            8,
            5,
            150,
            26449,
            2,
            19,
            348,
            469,
            3,
            2595,
            48,
            20740,
            246533,
            246533,
            19,
            30,
            5,
        ]  # Legal the president is a good guy and I don't want to lose my job. \n \n I have a

        output_ids = model.generate(input_ids, do_sample=False)
        self.assertListEqual(output_ids[0].numpy().tolist(), expected_output_ids)
