/**
 * Get number of instances of an element in an array.
 *
 * @param {Array} array The array to search.
 * @param {*} elementToCount The element to search for.
 * @returns {number} The number of instances of the element in the array.
 */
const getElementCount = function (array, elementToCount) {
  let count = 0
  for (let i = 0; i < array.length; i++) {
    if (array[i] === elementToCount) {
      count++
    }
  }
  return count
}

/**
 * Recursively flatten an array.
 *
 * @param {Array[]} array The array to flatten.
 * @return {Array} The flattened array.
 */
const flattenDeep = function (array) {
  return array.reduce(
    (accumulator, value) =>
      Array.isArray(value)
        ? accumulator.concat(flattenDeep(value))
        : accumulator.concat(value),
    [],
  )
}

/**
 * Return a scalar as a singleton array and an array as-is.
 *
 * @param {T|Array<T>} array An array or scalar.
 * @return {Array<T>} The original array or a singleton array of the scalar.
 */
const asArray = function (array) {
  return Array.isArray(array) ? array : [array]
}

module.exports = {
  getElementCount: getElementCount,
  flattenDeep: flattenDeep,
  asArray: asArray,
}
