from compressor.filters import CompilerFilter

class UglifyFilter(CompilerFilter):
    command = "uglifyjs -nc"