=======
History
=======

1.2.1 (2026-01-22)
------------------

🎉 Exciting New Features
```````````````````````

* Add parallel processing to `cubids apply` by @tientong98 in https://github.com/PennLINC/CuBIDS/pull/481
* Add parallelization to `cubids add-nifti-info` by @tientong98 in https://github.com/PennLINC/CuBIDS/pull/479
* Add `--n-cpus` to parallelize `cubids validate --validation-scope subject` by @tientong98 in https://github.com/PennLINC/CuBIDS/pull/476
* Support array-type metadata fields in `cubids group` by @tsalo in https://github.com/PennLINC/CuBIDS/pull/407
* Add file collection metadata as array-type fields to JSONs by @tsalo in https://github.com/PennLINC/CuBIDS/pull/445
* Add DWI sbref to cubids apply by @tientong98 in https://github.com/PennLINC/CuBIDS/pull/486

🐛 Bug Fixes
````````````

* Fix df created by `cubids group` and `cubids validate` by @tientong98 in https://github.com/PennLINC/CuBIDS/pull/483
* Fix M0 scan variant name inheritance by @singlesp in https://github.com/PennLINC/CuBIDS/pull/466
* Fix PARTICIPANT_ID_MISMATCH in `cubids validate` by @tientong98 in https://github.com/PennLINC/CuBIDS/pull/476

Other Changes
`````````````

* Refactor: Standardize bold-specific file handling for events, sbref, and physio by @tientong98 in https://github.com/PennLINC/CuBIDS/pull/484
* Change variant renaming from "ObliquityTrue" -> "Oblique" and "ObliquityFalse" -> "Plumb" by @tientong98 in https://github.com/PennLINC/CuBIDS/pull/480
* Remove deprecated CLIs by @tientong98 in https://github.com/PennLINC/CuBIDS/pull/454
* Update pybids requirement from <=0.19.0 to <=0.20.0 by @dependabot in https://github.com/PennLINC/CuBIDS/pull/468
* Update pandas requirement from <=2.2.3 to <=2.3.3 by @dependabot in https://github.com/PennLINC/CuBIDS/pull/469
* Update numpy requirement from <=2.2.3 to <=2.2.4 by @dependabot in https://github.com/PennLINC/CuBIDS/pull/453
* Update pybids requirement from <=0.18.1 to <=0.19.0 by @dependabot in https://github.com/PennLINC/CuBIDS/pull/451
* Update various GitHub Actions dependencies

**Full Changelog**: https://github.com/PennLINC/CuBIDS/compare/1.2.0...1.2.1

1.1.0 (2024-04-02)
------------------

🎉 Exciting New Features
````````````````````````

* Make CLI commands available as `cubids <command>` by @tsalo in https://github.com/PennLINC/CuBIDS/pull/268
* Add ASL fields to config by @tsalo in https://github.com/PennLINC/CuBIDS/pull/282

🐛 Bug Fixes
````````````

* Remove `--ignore_subject_consistency` param from `cubids validate` by @tsalo in https://github.com/PennLINC/CuBIDS/pull/276

Other Changes
`````````````

* Use black and isort to autoformat the main package by @tsalo in https://github.com/PennLINC/CuBIDS/pull/266
* Reorganize packaging and hopefully fix tests by @tsalo in https://github.com/PennLINC/CuBIDS/pull/267
* Move notebooks into example gallery by @tsalo in https://github.com/PennLINC/CuBIDS/pull/278
* Drop jinja and wrapt from dependencies and pin other requirements by @tsalo in https://github.com/PennLINC/CuBIDS/pull/295
* Run Pytests across all supported Python versions by @tsalo in https://github.com/PennLINC/CuBIDS/pull/279
* Improve documentation by @tsalo in https://github.com/PennLINC/CuBIDS/pull/290

New Contributors
````````````````

* @tsalo made their first contribution in https://github.com/PennLINC/CuBIDS/pull/266
* @dependabot made their first contribution in https://github.com/PennLINC/CuBIDS/pull/293

**Full Changelog**: https://github.com/PennLINC/CuBIDS/compare/1.0.2...1.0.3

1.0.2 (2023-09-07)
------------------

* Add image orientation by @scovitz in https://github.com/PennLINC/CuBIDS/pull/205
* review feedback milestone: adding code/CuBIDS option and converting CSVs to TSVs by @scovitz in https://github.com/PennLINC/CuBIDS/pull/217
* Reviewer feedback incorporated  into docs and pybids layout update by @scovitz in https://github.com/PennLINC/CuBIDS/pull/227
* Data dictionaries by @scovitz in https://github.com/PennLINC/CuBIDS/pull/230
* No index metadata by @scovitz in https://github.com/PennLINC/CuBIDS/pull/231
* updated _update_json to no longer use pybids by @scovitz in https://github.com/PennLINC/CuBIDS/pull/232
* Minor tune ups: codespell'ing (fixes + tox + CI (github actions)), remove of unintended to be committed 2 files by @yarikoptic in https://github.com/PennLINC/CuBIDS/pull/239
* ENH: Make "NumVolumes" an integer for 3D images by @cookpa in https://github.com/PennLINC/CuBIDS/pull/211
* adding note about fmap renamekeygroups by @megardn in https://github.com/PennLINC/CuBIDS/pull/140
* Update usage.rst by @megardn in https://github.com/PennLINC/CuBIDS/pull/138
* printing erroneous jsons and only rounding float parameters by @scovitz in https://github.com/PennLINC/CuBIDS/pull/257

New Contributors
`````````````````
* @yarikoptic made their first contribution in https://github.com/PennLINC/CuBIDS/pull/239
* @cookpa made their first contribution in https://github.com/PennLINC/CuBIDS/pull/211
* @megardn made their first contribution in https://github.com/PennLINC/CuBIDS/pull/140

**Full Changelog**: https://github.com/PennLINC/CuBIDS/compare/v1.0.1...1.0.2

0.1.0 (2020-10-07)
------------------

* First release on PyPI.
