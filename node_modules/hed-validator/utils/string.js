const date = require('date-and-time')
const parseISO = require('date-fns/parseISO')
const dateIsValid = require('date-fns/isValid')
const rfc3339ish = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(.\d+)?$/
const digitExpression = /^-?\d+(?:\.\d+)?(?:[Ee]-?\d+)?$/

/**
 * Check if a string is empty or only whitespace.
 *
 * @param {string} string The string to check.
 * @returns {boolean} Whether the string is empty.
 */
const stringIsEmpty = function (string) {
  return !string.trim()
}

/**
 * Get number of instances of an character in a string.
 *
 * @param {string} string The string to search.
 * @param {string} characterToCount The character to search for.
 * @returns {number} The number of instances of the character in the string.
 */
const getCharacterCount = function (string, characterToCount) {
  return string.split(characterToCount).length - 1
}

/**
 * Get a copy of a string with the first letter capitalized.
 *
 * @param {string} string The string to capitalize.
 * @returns {string} The capitalized string.
 */
const capitalizeString = function (string) {
  return string.charAt(0).toUpperCase() + string.substring(1)
}

/**
 * Determine if a string is a valid clock face time.
 *
 * @param {string} timeString The string to check.
 * @return {boolean} Whether the string is a valid clock face time.
 */
const isClockFaceTime = function (timeString) {
  return (
    date.isValid(timeString, 'HH:mm') || date.isValid(timeString, 'HH:mm:ss')
  )
}

/**
 * Determine if a string is a valid date-time.
 *
 * @param {string} dateTimeString The string to check.
 * @return {boolean} Whether the string is a valid date-time.
 */
const isDateTime = function (dateTimeString) {
  return (
    dateIsValid(parseISO(dateTimeString)) && rfc3339ish.test(dateTimeString)
  )
}

/**
 * Determine if a string is a valid number.
 *
 * @param {string} numericString The string to check.
 * @return {boolean} Whether the string is a valid number.
 */
const isNumber = function (numericString) {
  return digitExpression.test(numericString)
}

/**
 * Parse a template literal string.
 *
 * Copied from https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Template_literals.
 *
 * @param {string[]} strings The literal parts of the template string.
 * @param {(number|string)} keys The keys of the closure arguments.
 * @return {function(...[*]): string} A closure to fill the string template.
 */
const stringTemplate = function (strings, ...keys) {
  return function (...values) {
    let dict = values[values.length - 1] || {}
    let result = [strings[0]]
    keys.forEach(function (key, i) {
      let value = Number.isInteger(key) ? values[key] : dict[key]
      result.push(value, strings[i + 1])
    })
    return result.join('')
  }
}

module.exports = {
  stringIsEmpty: stringIsEmpty,
  getCharacterCount: getCharacterCount,
  capitalizeString: capitalizeString,
  isClockFaceTime: isClockFaceTime,
  isDateTime: isDateTime,
  isNumber: isNumber,
  stringTemplate: stringTemplate,
}
