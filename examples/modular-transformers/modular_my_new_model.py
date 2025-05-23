from myTransformers.models.llama.configuration_llama import LlamaConfig


# Example where we only want to only add a new config argument and new arg doc
# here there is no `ARG` so we are gonna take parent doc
class MyNewModelConfig(LlamaConfig):
    r"""
    new_param (`int`, *optional*, defaults to `False`):
        A fun new parameter
    """

    def __init__(self, mlp_bias=True, new_param=0, **super_kwargs):
        super().__init__(self, **super_kwargs)
        self.mlp_bias = mlp_bias
        self.new_param = new_param
