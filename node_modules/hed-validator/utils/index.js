// dependencies ------------------------------------------------------

const HED = require('./hed')
const array = require('./array')
const files = require('./files')
const string = require('./string')
const issues = require('./issues/issues')

// public api --------------------------------------------------------

const utils = {
  HED: HED,
  array: array,
  files: files,
  issues: issues,
  string: string,
}

// exports -----------------------------------------------------------

module.exports = utils
