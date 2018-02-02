@public
def fos() -> num:
    x = RLPList('\xc5\x83cow\x04', [bytes, num])
    return x[1]