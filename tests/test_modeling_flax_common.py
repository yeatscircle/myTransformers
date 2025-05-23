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

import copy
import inspect
import json
import random
import tempfile

import numpy as np

from myTransformers import is_flax_available
from myTransformers.models.auto import get_values
from myTransformers.testing_utils import CaptureLogger, require_flax
from myTransformers.utils import CONFIG_NAME, GENERATION_CONFIG_NAME, logging


if is_flax_available():
    import os

    import jax
    import jax.numpy as jnp
    from flax.core.frozen_dict import FrozenDict, freeze, unfreeze
    from flax.serialization import from_bytes
    from flax.traverse_util import flatten_dict, unflatten_dict

    from myTransformers import (
        FLAX_MODEL_FOR_QUESTION_ANSWERING_MAPPING,
        FLAX_MODEL_FOR_SEQUENCE_CLASSIFICATION_MAPPING,
        FLAX_MODEL_MAPPING,
        FlaxAutoModel,
        FlaxAutoModelForSequenceClassification,
        FlaxBertModel,
    )
    from myTransformers.modeling_flax_utils import FLAX_WEIGHTS_INDEX_NAME, FLAX_WEIGHTS_NAME

    os.environ["XLA_PYTHON_CLIENT_MEM_FRACTION"] = "0.12"  # assumed parallelism: 8


def ids_tensor(shape, vocab_size, rng=None):
    """Creates a random int32 tensor of the shape within the vocab size."""
    if rng is None:
        rng = random.Random()

    total_dims = 1
    for dim in shape:
        total_dims *= dim

    values = []
    for _ in range(total_dims):
        values.append(rng.randint(0, vocab_size - 1))

    output = np.array(values, dtype=jnp.int32).reshape(shape)

    return output


def floats_tensor(shape, scale=1.0, rng=None, name=None):
    """Creates a random float32 tensor"""
    if rng is None:
        rng = random.Random()

    total_dims = 1
    for dim in shape:
        total_dims *= dim

    values = []
    for _ in range(total_dims):
        values.append(rng.random() * scale)

    return np.array(values, dtype=jnp.float32).reshape(shape)


def random_attention_mask(shape, rng=None):
    attn_mask = ids_tensor(shape, vocab_size=2, rng=rng)
    # make sure that at least one token is attended to for each batch
    attn_mask[:, -1] = 1
    return attn_mask


def get_params(params, from_head_prefix=None):
    """Function extracts relevant parameters into flatten dict from model params,
    appends batch normalization statistics if present"""

    # If Both parameters and batch normalization statistics are present
    if "batch_stats" in params:
        # Extract only parameters for the specified head prefix (if specified) and add batch statistics
        if from_head_prefix is not None:
            extracted_params = flatten_dict(unfreeze(params["params"][from_head_prefix]))
            extracted_params.update(flatten_dict(params["batch_stats"][from_head_prefix]))
        else:
            extracted_params = flatten_dict(unfreeze(params["params"]))
            extracted_params.update(flatten_dict(params["batch_stats"]))

    # Only parameters are present
    else:
        if from_head_prefix is not None:
            extracted_params = flatten_dict(unfreeze(params[from_head_prefix]))
        else:
            extracted_params = flatten_dict(unfreeze(params))

    return extracted_params


@require_flax
class FlaxModelTesterMixin:
    model_tester = None
    all_model_classes = ()
    test_mismatched_shapes = True
    is_encoder_decoder = False
    test_head_masking = False
    has_attentions = True

    @property
    def all_generative_model_classes(self):
        return tuple(model_class for model_class in self.all_model_classes if model_class.can_generate())

    def _prepare_for_class(self, inputs_dict, model_class):
        inputs_dict = copy.deepcopy(inputs_dict)

        # hack for now until we have AutoModel classes
        if "ForMultipleChoice" in model_class.__name__:
            inputs_dict = {
                k: jnp.broadcast_to(v[:, None], (v.shape[0], self.model_tester.num_choices, v.shape[-1]))
                if isinstance(v, (jnp.ndarray, np.ndarray)) and k != "indices_prng_key"
                else v
                for k, v in inputs_dict.items()
            }

        return inputs_dict

    def assert_almost_equals(self, a: np.ndarray, b: np.ndarray, tol: float):
        diff = np.abs(a - b).max()
        self.assertLessEqual(diff, tol, f"Difference between torch and flax is {diff} (>= {tol}).")

    def test_model_outputs_equivalence(self):
        config, inputs_dict = self.model_tester.prepare_config_and_inputs_for_common()

        def check_equivalence(model, tuple_inputs, dict_inputs, additional_kwargs={}):
            tuple_output = model(**tuple_inputs, return_dict=False, **additional_kwargs)
            dict_output = model(**dict_inputs, return_dict=True, **additional_kwargs).to_tuple()

            def recursive_check(tuple_object, dict_object):
                if isinstance(tuple_object, (list, tuple)):
                    for tuple_iterable_value, dict_iterable_value in zip(tuple_object, dict_object):
                        recursive_check(tuple_iterable_value, dict_iterable_value)
                elif tuple_object is None:
                    return
                else:
                    self.assert_almost_equals(jnp.nan_to_num(tuple_object), jnp.nan_to_num(dict_object), 1e-5)

            recursive_check(tuple_output, dict_output)

        for model_class in self.all_model_classes:
            model = model_class(config)

            tuple_inputs = self._prepare_for_class(inputs_dict, model_class)
            dict_inputs = self._prepare_for_class(inputs_dict, model_class)
            check_equivalence(model, tuple_inputs, dict_inputs)

            tuple_inputs = self._prepare_for_class(inputs_dict, model_class)
            dict_inputs = self._prepare_for_class(inputs_dict, model_class)
            check_equivalence(model, tuple_inputs, dict_inputs, {"output_hidden_states": True})

    def test_from_pretrained_save_pretrained(self):
        config, inputs_dict = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            with self.subTest(model_class.__name__):
                model = model_class(config)

                prepared_inputs_dict = self._prepare_for_class(inputs_dict, model_class)
                outputs = model(**prepared_inputs_dict).to_tuple()

                # verify that normal save_pretrained works as expected
                with tempfile.TemporaryDirectory() as tmpdirname:
                    model.save_pretrained(tmpdirname)

                    # the config file (and the generation config file, if it can generate) should be saved
                    self.assertTrue(os.path.exists(os.path.join(tmpdirname, CONFIG_NAME)))
                    self.assertEqual(
                        model.can_generate(), os.path.exists(os.path.join(tmpdirname, GENERATION_CONFIG_NAME))
                    )

                    model_loaded = model_class.from_pretrained(tmpdirname)

                outputs_loaded = model_loaded(**prepared_inputs_dict).to_tuple()
                for output_loaded, output in zip(outputs_loaded, outputs):
                    self.assert_almost_equals(output_loaded, output, 1e-3)

                # verify that save_pretrained for distributed training
                # with `params=params` works as expected
                with tempfile.TemporaryDirectory() as tmpdirname:
                    model.save_pretrained(tmpdirname, params=model.params)
                    model_loaded = model_class.from_pretrained(tmpdirname)

                outputs_loaded = model_loaded(**prepared_inputs_dict).to_tuple()
                for output_loaded, output in zip(outputs_loaded, outputs):
                    self.assert_almost_equals(output_loaded, output, 1e-3)

    def test_save_load_from_base(self):
        config, _ = self.model_tester.prepare_config_and_inputs_for_common()
        base_class = FLAX_MODEL_MAPPING[config.__class__]

        for model_class in self.all_model_classes:
            if model_class == base_class:
                continue

            model = base_class(config)
            base_params = get_params(model.params)

            # check that all base model weights are loaded correctly
            with tempfile.TemporaryDirectory() as tmpdirname:
                model.save_pretrained(tmpdirname)
                head_model = model_class.from_pretrained(tmpdirname)

                base_param_from_head = get_params(head_model.params, from_head_prefix=head_model.base_model_prefix)

                for key in base_param_from_head.keys():
                    max_diff = (base_params[key] - base_param_from_head[key]).sum().item()
                    self.assertLessEqual(max_diff, 1e-3, msg=f"{key} not identical")

    def test_save_load_to_base(self):
        config, _ = self.model_tester.prepare_config_and_inputs_for_common()
        base_class = FLAX_MODEL_MAPPING[config.__class__]

        for model_class in self.all_model_classes:
            if model_class == base_class:
                continue

            model = model_class(config)
            base_params_from_head = get_params(model.params, from_head_prefix=model.base_model_prefix)

            # check that all base model weights are loaded correctly
            with tempfile.TemporaryDirectory() as tmpdirname:
                model.save_pretrained(tmpdirname)
                base_model = base_class.from_pretrained(tmpdirname)

                base_params = get_params(base_model.params)

                for key in base_params_from_head.keys():
                    max_diff = (base_params[key] - base_params_from_head[key]).sum().item()
                    self.assertLessEqual(max_diff, 1e-3, msg=f"{key} not identical")

    def test_jit_compilation(self):
        config, inputs_dict = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            with self.subTest(model_class.__name__):
                prepared_inputs_dict = self._prepare_for_class(inputs_dict, model_class)
                model = model_class(config)

                @jax.jit
                def model_jitted(input_ids, attention_mask=None, **kwargs):
                    return model(input_ids=input_ids, attention_mask=attention_mask, **kwargs)

                with self.subTest("JIT Enabled"):
                    jitted_outputs = model_jitted(**prepared_inputs_dict).to_tuple()

                with self.subTest("JIT Disabled"):
                    with jax.disable_jit():
                        outputs = model_jitted(**prepared_inputs_dict).to_tuple()

                self.assertEqual(len(outputs), len(jitted_outputs))
                for jitted_output, output in zip(jitted_outputs, outputs):
                    self.assertEqual(jitted_output.shape, output.shape)

    def test_forward_signature(self):
        config, _ = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            model = model_class(config)
            signature = inspect.signature(model.__call__)
            # signature.parameters is an OrderedDict => so arg_names order is deterministic
            arg_names = [*signature.parameters.keys()]

            if model.config.is_encoder_decoder:
                expected_arg_names = [
                    "input_ids",
                    "attention_mask",
                    "decoder_input_ids",
                    "decoder_attention_mask",
                ]
                self.assertListEqual(arg_names[: len(expected_arg_names)], expected_arg_names)
            else:
                expected_arg_names = ["input_ids", "attention_mask"]
                self.assertListEqual(arg_names[:2], expected_arg_names)

    def test_naming_convention(self):
        for model_class in self.all_model_classes:
            model_class_name = model_class.__name__
            module_class_name = (
                model_class_name[:-5] + "Module" if model_class_name[-5:] == "Model" else model_class_name + "Module"
            )
            bert_modeling_flax_module = __import__(model_class.__module__, fromlist=[module_class_name])
            module_cls = getattr(bert_modeling_flax_module, module_class_name)

            self.assertIsNotNone(module_cls)

    def test_hidden_states_output(self):
        def check_hidden_states_output(inputs_dict, config, model_class):
            model = model_class(config)
            outputs = model(**self._prepare_for_class(inputs_dict, model_class))
            hidden_states = outputs.encoder_hidden_states if config.is_encoder_decoder else outputs.hidden_states

            expected_num_layers = getattr(
                self.model_tester, "expected_num_hidden_layers", self.model_tester.num_hidden_layers + 1
            )
            self.assertEqual(len(hidden_states), expected_num_layers)

            if hasattr(self.model_tester, "encoder_seq_length"):
                seq_length = self.model_tester.encoder_seq_length
            else:
                seq_length = self.model_tester.seq_length

            self.assertListEqual(
                list(hidden_states[0].shape[-2:]),
                [seq_length, self.model_tester.hidden_size],
            )

            if config.is_encoder_decoder:
                hidden_states = outputs.decoder_hidden_states

                self.assertIsInstance(hidden_states, (list, tuple))
                self.assertEqual(len(hidden_states), expected_num_layers)
                seq_len = getattr(self.model_tester, "seq_length", None)
                decoder_seq_length = getattr(self.model_tester, "decoder_seq_length", seq_len)

                self.assertListEqual(
                    list(hidden_states[0].shape[-2:]),
                    [decoder_seq_length, self.model_tester.hidden_size],
                )

        config, inputs_dict = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            inputs_dict["output_hidden_states"] = True
            check_hidden_states_output(inputs_dict, config, model_class)

            # check that output_hidden_states also work using config
            del inputs_dict["output_hidden_states"]
            config.output_hidden_states = True

            check_hidden_states_output(inputs_dict, config, model_class)

    def test_attention_outputs(self):
        if not self.has_attentions:
            self.skipTest(reason="Model does not output attentions")

        config, inputs_dict = self.model_tester.prepare_config_and_inputs_for_common()
        config.return_dict = True

        seq_length = getattr(self.model_tester, "seq_length", None)
        decoder_seq_length = getattr(self.model_tester, "decoder_seq_length", seq_length)
        encoder_seq_length = getattr(self.model_tester, "encoder_seq_length", seq_length)
        decoder_key_length = getattr(self.model_tester, "decoder_key_length", decoder_seq_length)
        encoder_key_length = getattr(self.model_tester, "key_length", encoder_seq_length)

        for model_class in self.all_model_classes:
            inputs_dict["output_attentions"] = True
            inputs_dict["output_hidden_states"] = False
            model = model_class(config)
            outputs = model(**self._prepare_for_class(inputs_dict, model_class))
            attentions = outputs.encoder_attentions if config.is_encoder_decoder else outputs.attentions
            self.assertEqual(len(attentions), self.model_tester.num_hidden_layers)

            # check that output_attentions also work using config
            del inputs_dict["output_attentions"]
            config.output_attentions = True
            model = model_class(config)
            outputs = model(**self._prepare_for_class(inputs_dict, model_class))
            attentions = outputs.encoder_attentions if config.is_encoder_decoder else outputs.attentions
            self.assertEqual(len(attentions), self.model_tester.num_hidden_layers)

            self.assertListEqual(
                list(attentions[0].shape[-3:]),
                [self.model_tester.num_attention_heads, encoder_seq_length, encoder_key_length],
            )
            out_len = len(outputs)

            if self.is_encoder_decoder:
                correct_outlen = 5

                # Question Answering model returns start_logits and end_logits
                if model_class in get_values(FLAX_MODEL_FOR_QUESTION_ANSWERING_MAPPING):
                    correct_outlen += 1  # start_logits and end_logits instead of only 1 output

                self.assertEqual(out_len, correct_outlen)

                # decoder attentions
                decoder_attentions = outputs.decoder_attentions
                self.assertIsInstance(decoder_attentions, (list, tuple))
                self.assertEqual(len(decoder_attentions), self.model_tester.num_hidden_layers)
                self.assertListEqual(
                    list(decoder_attentions[0].shape[-3:]),
                    [self.model_tester.num_attention_heads, decoder_seq_length, decoder_key_length],
                )

                # cross attentions
                cross_attentions = outputs.cross_attentions
                self.assertIsInstance(cross_attentions, (list, tuple))
                self.assertEqual(len(cross_attentions), self.model_tester.num_hidden_layers)
                self.assertListEqual(
                    list(cross_attentions[0].shape[-3:]),
                    [
                        self.model_tester.num_attention_heads,
                        decoder_seq_length,
                        encoder_key_length,
                    ],
                )

            # Check attention is always last and order is fine
            inputs_dict["output_attentions"] = True
            inputs_dict["output_hidden_states"] = True
            model = model_class(config)
            outputs = model(**self._prepare_for_class(inputs_dict, model_class))

            if hasattr(self.model_tester, "num_hidden_states_types"):
                added_hidden_states = self.model_tester.num_hidden_states_types
            elif self.is_encoder_decoder:
                added_hidden_states = 2
            else:
                added_hidden_states = 1
            self.assertEqual(out_len + added_hidden_states, len(outputs))

            self_attentions = outputs.encoder_attentions if config.is_encoder_decoder else outputs.attentions
            self.assertEqual(len(self_attentions), self.model_tester.num_hidden_layers)

            self.assertListEqual(
                list(self_attentions[0].shape[-3:]),
                [self.model_tester.num_attention_heads, encoder_seq_length, encoder_key_length],
            )

    def test_load_with_mismatched_shapes(self):
        if not self.test_mismatched_shapes:
            return
        config, inputs_dict = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            if model_class not in get_values(FLAX_MODEL_FOR_SEQUENCE_CLASSIFICATION_MAPPING):
                continue

            with self.subTest(msg=f"Testing {model_class}"):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    model = model_class(config)
                    model.save_pretrained(tmp_dir)

                    # Fails when we don't set ignore_mismatched_sizes=True
                    with self.assertRaises(ValueError):
                        new_model = FlaxAutoModelForSequenceClassification.from_pretrained(tmp_dir, num_labels=42)
                    with self.assertRaises(ValueError):
                        new_model_without_prefix = FlaxAutoModel.from_pretrained(tmp_dir, vocab_size=10)

                    logger = logging.get_logger("myTransformers.modeling_flax_utils")
                    with CaptureLogger(logger) as cl:
                        new_model = FlaxAutoModelForSequenceClassification.from_pretrained(
                            tmp_dir, num_labels=42, ignore_mismatched_sizes=True
                        )
                    self.assertIn("the shapes did not match", cl.out)

                    logits = new_model(**inputs_dict)["logits"]
                    self.assertEqual(logits.shape[1], 42)

                    with CaptureLogger(logger) as cl:
                        new_model_without_prefix = FlaxAutoModel.from_pretrained(
                            tmp_dir, vocab_size=10, ignore_mismatched_sizes=True
                        )
                    self.assertIn("the shapes did not match", cl.out)
                    input_ids = ids_tensor((2, 8), 10)
                    if self.is_encoder_decoder:
                        new_model_without_prefix(input_ids, decoder_input_ids=input_ids)
                    else:
                        new_model_without_prefix(input_ids)

    def test_default_params_dtype(self):
        config, _ = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            # check if all params are still in float32 when dtype of computation is half-precision
            model = model_class(config, dtype=jnp.float16)
            types = jax.tree_util.tree_map(lambda x: x.dtype, model.params)
            types = flatten_dict(types)

            for name, type_ in types.items():
                self.assertEqual(type_, jnp.float32, msg=f"param {name} is not initialized in fp32.")

    def test_to_bf16(self):
        config, _ = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            model = model_class(config)

            # cast all params to bf16
            params = model.to_bf16(model.params)
            types = flatten_dict(jax.tree_util.tree_map(lambda x: x.dtype, params))
            # test if all params are in bf16
            for name, type_ in types.items():
                self.assertEqual(type_, jnp.bfloat16, msg=f"param {name} is not in bf16.")

            # test masking
            flat_params = flatten_dict(params)
            key = random.choice(list(flat_params.keys()))  # choose a random param
            mask = {path: path != key for path in flat_params}  # don't cast the key
            mask = unflatten_dict(mask)

            params = model.to_bf16(model.params, mask)
            types = flatten_dict(jax.tree_util.tree_map(lambda x: x.dtype, params))
            # test if all params are in bf16 except key
            for name, type_ in types.items():
                if name == key:
                    self.assertEqual(type_, jnp.float32, msg=f"param {name} should be in fp32.")
                else:
                    self.assertEqual(type_, jnp.bfloat16, msg=f"param {name} is not in bf16.")

    def test_to_fp16(self):
        config, _ = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            model = model_class(config)

            # cast all params to fp16
            params = model.to_fp16(model.params)
            types = flatten_dict(jax.tree_util.tree_map(lambda x: x.dtype, params))
            # test if all params are in fp16
            for name, type_ in types.items():
                self.assertEqual(type_, jnp.float16, msg=f"param {name} is not in fp16.")

            # test masking
            flat_params = flatten_dict(params)
            key = random.choice(list(flat_params.keys()))  # choose a random param
            mask = {path: path != key for path in flat_params}  # don't cast the key
            mask = unflatten_dict(mask)

            params = model.to_fp16(model.params, mask)
            types = flatten_dict(jax.tree_util.tree_map(lambda x: x.dtype, params))
            # test if all params are in fp16 except key
            for name, type_ in types.items():
                if name == key:
                    self.assertEqual(type_, jnp.float32, msg=f"param {name} should be in fp32.")
                else:
                    self.assertEqual(type_, jnp.float16, msg=f"param {name} is not in fp16.")

    def test_to_fp32(self):
        config, _ = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            model = model_class(config)

            # cast all params to fp16 and back to fp32
            params = model.to_fp16(model.params)
            params = model.to_fp32(params)

            # test if all params are in fp32
            types = flatten_dict(jax.tree_util.tree_map(lambda x: x.dtype, params))
            for name, type_ in types.items():
                self.assertEqual(type_, jnp.float32, msg=f"param {name} is not in fp32.")

            # test masking
            flat_params = flatten_dict(params)
            key = random.choice(list(flat_params.keys()))  # choose a random param
            mask = {path: path != key for path in flat_params}  # don't cast the key
            mask = unflatten_dict(mask)

            # cast to fp16 and back to fp32 with mask
            params = model.to_fp16(model.params)
            params = model.to_fp32(params, mask)

            # test if all params are in fp32 except key
            types = flatten_dict(jax.tree_util.tree_map(lambda x: x.dtype, params))
            for name, type_ in types.items():
                if name == key:
                    self.assertEqual(type_, jnp.float16, msg=f"param {name} should be in fp16.")
                else:
                    self.assertEqual(type_, jnp.float32, msg=f"param {name} is not in fp32.")

    def test_save_load_in_fp16(self):
        config, _ = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            model = model_class(config)

        # convert weights to fp16 and save
        params = model.to_fp16(model.params)
        with tempfile.TemporaryDirectory() as tmpdirname:
            model.save_pretrained(tmpdirname, params=params)

            # load the weights again and check if they are still in fp16
            model = model_class.from_pretrained(tmpdirname)
            types = flatten_dict(jax.tree_util.tree_map(lambda x: x.dtype, model.params))
            for name, type_ in types.items():
                self.assertEqual(type_, jnp.float16, msg=f"param {name} is not in fp16.")

    def test_save_load_in_bf16(self):
        config, _ = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            model = model_class(config)

        # convert weights to bf16 and save
        params = model.to_bf16(model.params)
        with tempfile.TemporaryDirectory() as tmpdirname:
            model.save_pretrained(tmpdirname, params=params)

            # load the weights again and check if they are still in fp16
            model = model_class.from_pretrained(tmpdirname)
            types = flatten_dict(jax.tree_util.tree_map(lambda x: x.dtype, model.params))
            for name, type_ in types.items():
                self.assertEqual(type_, jnp.bfloat16, msg=f"param {name} is not in bf16.")

    def test_model_main_input_name(self):
        for model_class in self.all_model_classes:
            model_signature = inspect.signature(getattr(model_class, "__call__"))
            # The main input is the name of the argument after `self`
            observed_main_input_name = list(model_signature.parameters.keys())[1]
            self.assertEqual(model_class.main_input_name, observed_main_input_name)

    def test_headmasking(self):
        if not self.test_head_masking:
            return
        config, inputs_dict = self.model_tester.prepare_config_and_inputs_for_common()
        config.return_dict = True

        def _prepare_layer_head_mask(i, attention_heads, num_hidden_layers):
            if i == 0:
                return np.concatenate([np.zeros(1, dtype=jnp.int32), np.ones(attention_heads - 1, dtype=jnp.int32)])
            if i == num_hidden_layers - 1:
                return np.concatenate([np.zeros(attention_heads - 1, dtype=jnp.int32), np.ones(1, dtype=jnp.int32)])
            return np.ones(attention_heads, dtype=jnp.int32)

        for model_class in self.all_model_classes:
            model = model_class(config)

            inputs_dict["output_attentions"] = True
            inputs_dict["output_hidden_states"] = False
            inputs = self._prepare_for_class(inputs_dict, model_class).copy()
            # Prepare head mask
            inputs["head_mask"] = np.stack(
                [
                    _prepare_layer_head_mask(i, config.num_attention_heads, config.num_hidden_layers)
                    for i in range(config.num_hidden_layers)
                ]
            )
            outputs = model(**inputs)

            def _check_attentions_validity(attentions):
                # Remove NaN
                for t in attentions:
                    # Check we don't have more than 25% nans (arbitrary)
                    self.assertLess(np.isnan(t).sum(), t.size / 4)
                attentions = [np.where(np.isnan(t), 0.0, t) for t in attentions]

                self.assertAlmostEqual(attentions[0][..., 0, :, :].sum(), 0.0)
                self.assertNotEqual(attentions[0][..., -1, :, :].sum(), 0.0)
                if len(attentions) > 2:  # encoder-decodere models have only 2 layers in each modules
                    self.assertNotEqual(attentions[1][..., 0, :, :].sum(), 0.0)
                self.assertAlmostEqual(attentions[-1][..., -2, :, :].sum(), 0.0)
                self.assertNotEqual(attentions[-1][..., -1, :, :].sum(), 0.0)

            if model.config.is_encoder_decoder:
                raise NotImplementedError("The test has not been implemented for encoder-decoder models yet.")
            else:
                _check_attentions_validity(outputs.attentions)

    def test_no_automatic_init(self):
        config, inputs_dict = self.model_tester.prepare_config_and_inputs_for_common()
        config.return_dict = True

        for model_class in self.all_model_classes:
            model = model_class(config, _do_init=False)

            # Check that accessing params raises an ValueError when _do_init is False
            with self.assertRaises(ValueError):
                params = model.params

            # Check if we params can be properly initialized when calling init_weights
            params = model.init_weights(model.key, model.input_shape)
            assert isinstance(params, (dict, FrozenDict)), f"params are not an instance of {FrozenDict}"
            # Check if all required params are initialized
            keys = set(flatten_dict(unfreeze(params)).keys())
            self.assertTrue(all(k in keys for k in model.required_params))
            # Check if the shapes match
            flat_params = flatten_dict(unfreeze(params))
            for k, v in flatten_dict(unfreeze(model.params_shape_tree)).items():
                self.assertEqual(
                    v.shape,
                    flat_params[k].shape,
                    f"Shapes of {k} do not match. Expecting {v.shape}, got {flat_params[k].shape}.",
                )

            # Check that setting params raises an ValueError when _do_init is False
            with self.assertRaises(ValueError):
                model.params = params

            # Check if we can do a forward pass
            inputs_dict["output_hidden_states"] = True
            inputs = self._prepare_for_class(inputs_dict, model_class).copy()
            model(**inputs, params=params)

    def test_from_pretrained_with_no_automatic_init(self):
        config, inputs_dict = self.model_tester.prepare_config_and_inputs_for_common()
        config.return_dict = True

        def _assert_all_params_initialised(model, params):
            # Check if all required params are loaded
            keys = set(flatten_dict(unfreeze(params)).keys())
            self.assertTrue(all(k in keys for k in model.required_params))
            # Check if the shapes match
            flat_params = flatten_dict(unfreeze(params))
            for k, v in flatten_dict(unfreeze(model.params_shape_tree)).items():
                self.assertEqual(
                    v.shape,
                    flat_params[k].shape,
                    f"Shapes of {k} do not match. Expecting {v.shape}, got {flat_params[k].shape}.",
                )

        for model_class in self.all_model_classes:
            # init the model
            model = model_class(config)

            # save the model in the temporary directory
            # load the saved model with _do_init=False
            with tempfile.TemporaryDirectory() as tmpdirname:
                model.save_pretrained(tmpdirname)
                model, params = model_class.from_pretrained(tmpdirname, _do_init=False)

            # Check that accessing params raises an ValueError when _do_init is False
            with self.assertRaises(ValueError):
                params = model.params

            # Check if all required params are loaded
            _assert_all_params_initialised(model, params)

            # Check that setting params raises an ValueError when _do_init is False
            with self.assertRaises(ValueError):
                model.params = params

            # Check if init_weights initializes missing keys from from_pretrained
            flat_params = flatten_dict(unfreeze(params))
            random_key = random.choice(list(flat_params.keys()))
            flat_params.pop(random_key)
            params = freeze(unflatten_dict(flat_params))

            with tempfile.TemporaryDirectory() as tmpdirname:
                model.save_pretrained(tmpdirname, params=params)
                model, params = model_class.from_pretrained(tmpdirname, _do_init=False)

                params = model.init_weights(model.key, model.input_shape, params=params)
                # Check if all required params are loaded
                _assert_all_params_initialised(model, params)

    def test_checkpoint_sharding_from_hub(self):
        model = FlaxBertModel.from_pretrained("ArthurZ/flax-tiny-random-bert-sharded")
        # the model above is the same as the model below, just a sharded version.
        ref_model = FlaxBertModel.from_pretrained("hf-internal-testing/tiny-bert-flax-only")
        for p1, p2 in zip(flatten_dict(model.params).values(), flatten_dict(ref_model.params).values()):
            assert np.allclose(np.array(p1), np.array(p2))

    def test_checkpoint_sharding_local(self):
        model = FlaxBertModel.from_pretrained("hf-internal-testing/tiny-bert-flax-only")

        with tempfile.TemporaryDirectory() as tmp_dir:
            # We use the same folder for various sizes to make sure a new save erases the old checkpoint.
            for max_size in ["150kB", "150kiB", "200kB", "200kiB"]:
                model.save_pretrained(tmp_dir, max_shard_size=max_size)

                # Get each shard file and its size
                shard_to_size = {}
                for shard in os.listdir(tmp_dir):
                    if shard.endswith(".msgpack"):
                        shard_file = os.path.join(tmp_dir, shard)
                        shard_to_size[shard_file] = os.path.getsize(shard_file)

                index_file = os.path.join(tmp_dir, FLAX_WEIGHTS_INDEX_NAME)
                # Check there is an index but no regular weight file
                self.assertTrue(os.path.isfile(index_file))
                self.assertFalse(os.path.isfile(os.path.join(tmp_dir, FLAX_WEIGHTS_NAME)))

                # Check a file is bigger than max_size only when it has a single weight
                for shard_file, size in shard_to_size.items():
                    if max_size.endswith("kiB"):
                        max_size_int = int(max_size[:-3]) * 2**10
                    else:
                        max_size_int = int(max_size[:-2]) * 10**3
                    # Note: pickle adds some junk so the weight of the file can end up being slightly bigger than
                    # the size asked for (since we count parameters)
                    if size >= max_size_int + 50000:
                        with open(shard_file, "rb") as state_f:
                            state_file = from_bytes(FlaxBertModel, state_f.read())
                            self.assertEqual(len(state_file), 1)

                # Check the index and the shard files found match
                with open(index_file, encoding="utf-8") as f:
                    index = json.loads(f.read())

                all_shards = set(index["weight_map"].values())
                shards_found = {f for f in os.listdir(tmp_dir) if f.endswith(".msgpack")}
                self.assertSetEqual(all_shards, shards_found)

                # Finally, check the model can be reloaded
                new_model = FlaxBertModel.from_pretrained(tmp_dir)
                for p1, p2 in zip(flatten_dict(model.params).values(), flatten_dict(new_model.params).values()):
                    self.assertTrue(np.allclose(np.array(p1), np.array(p2)))

    def test_gradient_checkpointing(self):
        config, inputs_dict = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            # prepare inputs
            prepared_inputs_dict = self._prepare_for_class(inputs_dict, model_class)
            model = model_class(config)
            remat_model = model_class(config)

            try:
                remat_model.enable_gradient_checkpointing()
            except NotImplementedError:
                continue

            outputs = model(**prepared_inputs_dict)
            remat_outputs = remat_model(**prepared_inputs_dict)

            # ensure that the dicts of outputs contain the same keys
            self.assertEqual(outputs.keys(), remat_outputs.keys())

            outputs = outputs.to_tuple()
            remat_outputs = remat_outputs.to_tuple()

            # ensure that the outputs remain precisely equal
            for output, remat_output in zip(outputs, remat_outputs):
                self.assertTrue((output == remat_output).all())
