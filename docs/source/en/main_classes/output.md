<!--Copyright 2020 The HuggingFace Team. All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with
the License. You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

⚠️ Note that this file is in Markdown but contain specific syntax for our doc-builder (similar to MDX) that may not be
rendered properly in your Markdown viewer.

-->

# Model outputs

All models have outputs that are instances of subclasses of [`~utils.ModelOutput`]. Those are
data structures containing all the information returned by the model, but that can also be used as tuples or
dictionaries.

Let's see how this looks in an example:

```python
from myTransformers import BertTokenizer, BertForSequenceClassification
import torch

tokenizer = BertTokenizer.from_pretrained("google-bert/bert-base-uncased")
model = BertForSequenceClassification.from_pretrained("google-bert/bert-base-uncased")

inputs = tokenizer("Hello, my dog is cute", return_tensors="pt")
labels = torch.tensor([1]).unsqueeze(0)  # Batch size 1
outputs = model(**inputs, labels=labels)
```

The `outputs` object is a [`~modeling_outputs.SequenceClassifierOutput`], as we can see in the
documentation of that class below, it means it has an optional `loss`, a `logits`, an optional `hidden_states` and
an optional `attentions` attribute. Here we have the `loss` since we passed along `labels`, but we don't have
`hidden_states` and `attentions` because we didn't pass `output_hidden_states=True` or
`output_attentions=True`.

<Tip>

When passing `output_hidden_states=True` you may expect the `outputs.hidden_states[-1]` to match `outputs.last_hidden_state` exactly.
However, this is not always the case. Some models apply normalization or subsequent process to the last hidden state when it's returned.

</Tip>


You can access each attribute as you would usually do, and if that attribute has not been returned by the model, you
will get `None`. Here for instance `outputs.loss` is the loss computed by the model, and `outputs.attentions` is
`None`.

When considering our `outputs` object as tuple, it only considers the attributes that don't have `None` values.
Here for instance, it has two elements, `loss` then `logits`, so

```python
outputs[:2]
```

will return the tuple `(outputs.loss, outputs.logits)` for instance.

When considering our `outputs` object as dictionary, it only considers the attributes that don't have `None`
values. Here for instance, it has two keys that are `loss` and `logits`.

We document here the generic model outputs that are used by more than one model type. Specific output types are
documented on their corresponding model page.

## ModelOutput

[[autodoc]] utils.ModelOutput
    - to_tuple

## BaseModelOutput

[[autodoc]] modeling_outputs.BaseModelOutput

## BaseModelOutputWithPooling

[[autodoc]] modeling_outputs.BaseModelOutputWithPooling

## BaseModelOutputWithCrossAttentions

[[autodoc]] modeling_outputs.BaseModelOutputWithCrossAttentions

## BaseModelOutputWithPoolingAndCrossAttentions

[[autodoc]] modeling_outputs.BaseModelOutputWithPoolingAndCrossAttentions

## BaseModelOutputWithPast

[[autodoc]] modeling_outputs.BaseModelOutputWithPast

## BaseModelOutputWithPastAndCrossAttentions

[[autodoc]] modeling_outputs.BaseModelOutputWithPastAndCrossAttentions

## Seq2SeqModelOutput

[[autodoc]] modeling_outputs.Seq2SeqModelOutput

## CausalLMOutput

[[autodoc]] modeling_outputs.CausalLMOutput

## CausalLMOutputWithCrossAttentions

[[autodoc]] modeling_outputs.CausalLMOutputWithCrossAttentions

## CausalLMOutputWithPast

[[autodoc]] modeling_outputs.CausalLMOutputWithPast

## MaskedLMOutput

[[autodoc]] modeling_outputs.MaskedLMOutput

## Seq2SeqLMOutput

[[autodoc]] modeling_outputs.Seq2SeqLMOutput

## NextSentencePredictorOutput

[[autodoc]] modeling_outputs.NextSentencePredictorOutput

## SequenceClassifierOutput

[[autodoc]] modeling_outputs.SequenceClassifierOutput

## Seq2SeqSequenceClassifierOutput

[[autodoc]] modeling_outputs.Seq2SeqSequenceClassifierOutput

## MultipleChoiceModelOutput

[[autodoc]] modeling_outputs.MultipleChoiceModelOutput

## TokenClassifierOutput

[[autodoc]] modeling_outputs.TokenClassifierOutput

## QuestionAnsweringModelOutput

[[autodoc]] modeling_outputs.QuestionAnsweringModelOutput

## Seq2SeqQuestionAnsweringModelOutput

[[autodoc]] modeling_outputs.Seq2SeqQuestionAnsweringModelOutput

## Seq2SeqSpectrogramOutput

[[autodoc]] modeling_outputs.Seq2SeqSpectrogramOutput

## SemanticSegmenterOutput

[[autodoc]] modeling_outputs.SemanticSegmenterOutput

## ImageClassifierOutput

[[autodoc]] modeling_outputs.ImageClassifierOutput

## ImageClassifierOutputWithNoAttention

[[autodoc]] modeling_outputs.ImageClassifierOutputWithNoAttention

## DepthEstimatorOutput

[[autodoc]] modeling_outputs.DepthEstimatorOutput

## Wav2Vec2BaseModelOutput

[[autodoc]] modeling_outputs.Wav2Vec2BaseModelOutput

## XVectorOutput

[[autodoc]] modeling_outputs.XVectorOutput

## Seq2SeqTSModelOutput

[[autodoc]] modeling_outputs.Seq2SeqTSModelOutput

## Seq2SeqTSPredictionOutput

[[autodoc]] modeling_outputs.Seq2SeqTSPredictionOutput

## SampleTSPredictionOutput

[[autodoc]] modeling_outputs.SampleTSPredictionOutput

## TFBaseModelOutput

[[autodoc]] modeling_tf_outputs.TFBaseModelOutput

## TFBaseModelOutputWithPooling

[[autodoc]] modeling_tf_outputs.TFBaseModelOutputWithPooling

## TFBaseModelOutputWithPoolingAndCrossAttentions

[[autodoc]] modeling_tf_outputs.TFBaseModelOutputWithPoolingAndCrossAttentions

## TFBaseModelOutputWithPast

[[autodoc]] modeling_tf_outputs.TFBaseModelOutputWithPast

## TFBaseModelOutputWithPastAndCrossAttentions

[[autodoc]] modeling_tf_outputs.TFBaseModelOutputWithPastAndCrossAttentions

## TFSeq2SeqModelOutput

[[autodoc]] modeling_tf_outputs.TFSeq2SeqModelOutput

## TFCausalLMOutput

[[autodoc]] modeling_tf_outputs.TFCausalLMOutput

## TFCausalLMOutputWithCrossAttentions

[[autodoc]] modeling_tf_outputs.TFCausalLMOutputWithCrossAttentions

## TFCausalLMOutputWithPast

[[autodoc]] modeling_tf_outputs.TFCausalLMOutputWithPast

## TFMaskedLMOutput

[[autodoc]] modeling_tf_outputs.TFMaskedLMOutput

## TFSeq2SeqLMOutput

[[autodoc]] modeling_tf_outputs.TFSeq2SeqLMOutput

## TFNextSentencePredictorOutput

[[autodoc]] modeling_tf_outputs.TFNextSentencePredictorOutput

## TFSequenceClassifierOutput

[[autodoc]] modeling_tf_outputs.TFSequenceClassifierOutput

## TFSeq2SeqSequenceClassifierOutput

[[autodoc]] modeling_tf_outputs.TFSeq2SeqSequenceClassifierOutput

## TFMultipleChoiceModelOutput

[[autodoc]] modeling_tf_outputs.TFMultipleChoiceModelOutput

## TFTokenClassifierOutput

[[autodoc]] modeling_tf_outputs.TFTokenClassifierOutput

## TFQuestionAnsweringModelOutput

[[autodoc]] modeling_tf_outputs.TFQuestionAnsweringModelOutput

## TFSeq2SeqQuestionAnsweringModelOutput

[[autodoc]] modeling_tf_outputs.TFSeq2SeqQuestionAnsweringModelOutput

## FlaxBaseModelOutput

[[autodoc]] modeling_flax_outputs.FlaxBaseModelOutput

## FlaxBaseModelOutputWithPast

[[autodoc]] modeling_flax_outputs.FlaxBaseModelOutputWithPast

## FlaxBaseModelOutputWithPooling

[[autodoc]] modeling_flax_outputs.FlaxBaseModelOutputWithPooling

## FlaxBaseModelOutputWithPastAndCrossAttentions

[[autodoc]] modeling_flax_outputs.FlaxBaseModelOutputWithPastAndCrossAttentions

## FlaxSeq2SeqModelOutput

[[autodoc]] modeling_flax_outputs.FlaxSeq2SeqModelOutput

## FlaxCausalLMOutputWithCrossAttentions

[[autodoc]] modeling_flax_outputs.FlaxCausalLMOutputWithCrossAttentions

## FlaxMaskedLMOutput

[[autodoc]] modeling_flax_outputs.FlaxMaskedLMOutput

## FlaxSeq2SeqLMOutput

[[autodoc]] modeling_flax_outputs.FlaxSeq2SeqLMOutput

## FlaxNextSentencePredictorOutput

[[autodoc]] modeling_flax_outputs.FlaxNextSentencePredictorOutput

## FlaxSequenceClassifierOutput

[[autodoc]] modeling_flax_outputs.FlaxSequenceClassifierOutput

## FlaxSeq2SeqSequenceClassifierOutput

[[autodoc]] modeling_flax_outputs.FlaxSeq2SeqSequenceClassifierOutput

## FlaxMultipleChoiceModelOutput

[[autodoc]] modeling_flax_outputs.FlaxMultipleChoiceModelOutput

## FlaxTokenClassifierOutput

[[autodoc]] modeling_flax_outputs.FlaxTokenClassifierOutput

## FlaxQuestionAnsweringModelOutput

[[autodoc]] modeling_flax_outputs.FlaxQuestionAnsweringModelOutput

## FlaxSeq2SeqQuestionAnsweringModelOutput

[[autodoc]] modeling_flax_outputs.FlaxSeq2SeqQuestionAnsweringModelOutput
