from myTransformers import BertTokenizerFast

from .custom_tokenization import CustomTokenizer


class CustomTokenizerFast(BertTokenizerFast):
    slow_tokenizer_class = CustomTokenizer
    pass
