=====
Usage
=====

`os-traits` is primarily composed of a set of constants that may be referenced
by simply importing the ``os_traits`` module and referencing one of the
module's traits constants::

    $ python
    Python 2.7.11+ (default, Apr 17 2016, 14:00:29)
    [GCC 5.3.1 20160413] on linux2
    Type "help", "copyright", "credits" or "license" for more information.
    >>> import os_traits as ot
    >>> print ot.HW_CPU_X86_SSE42
    HW_CPU_X86_SSE42

You can get a list of the ``os_traits`` symbols by simply doing a
``dir(os_traits)``.

Want to see the trait strings for a subset of traits? There's a method for that
too::

    >>> import pprint
    >>> pprint.pprint(ot.get_traits(prefix='HW_CPU_X86_'))
    ['HW_CPU_X86_FMA3',
    'HW_CPU_X86_AVX',
    'HW_CPU_X86_MMX',
    'HW_CPU_X86_MPX',
    'HW_CPU_X86_CLMUL',
    'HW_CPU_X86_AVX512VL',
    'HW_CPU_X86_AVX512CD',
    'HW_CPU_X86_BMI',
    'HW_CPU_X86_AVX512DQ',
    'HW_CPU_X86_SSE3',
    'HW_CPU_X86_ABM',
    'HW_CPU_X86_SSE4A',
    'HW_CPU_X86_AESNI',
    'HW_CPU_X86_F16C',
    'HW_CPU_X86_VMX',
    'HW_CPU_X86_SVM',
    'HW_CPU_X86_TSX',
    'HW_CPU_X86_AVX512PF',
    'HW_CPU_X86_SSE41',
    'HW_CPU_X86_ASF',
    'HW_CPU_X86_SGX',
    'HW_CPU_X86_SSE',
    'HW_CPU_X86_SSSE3',
    'HW_CPU_X86_SHA',
    'HW_CPU_X86_TBM',
    'HW_CPU_X86_SSE42',
    'HW_CPU_X86_3DNOW',
    'HW_CPU_X86_BMI2',
    'HW_CPU_X86_AVX512BW',
    'HW_CPU_X86_XOP',
    'HW_CPU_X86_AVX2',
    'HW_CPU_X86_AVX512F',
    'HW_CPU_X86_SSE2',
    'HW_CPU_X86_FMA4',
    'HW_CPU_X86_AVX512ER']
