const assert = require('assert')
const utils = require('../')

describe('Element counts', function() {
  it('must be correct', function() {
    const testArray = [
      'a',
      'b',
      'c',
      'a',
      'b',
      'c',
      'a',
      'a',
      'a',
      'b',
      'c',
      'c',
      'c',
      'c',
      'd',
      'd',
      'd',
      'f',
      'd',
      'd',
      'd',
      'd',
    ]
    const resultA = utils.array.getElementCount(testArray, 'a')
    const resultB = utils.array.getElementCount(testArray, 'b')
    const resultC = utils.array.getElementCount(testArray, 'c')
    const resultD = utils.array.getElementCount(testArray, 'd')
    const resultE = utils.array.getElementCount(testArray, 'e')
    const resultF = utils.array.getElementCount(testArray, 'f')
    assert.strictEqual(resultA, 5)
    assert.strictEqual(resultB, 3)
    assert.strictEqual(resultC, 6)
    assert.strictEqual(resultD, 7)
    assert.strictEqual(resultE, 0)
    assert.strictEqual(resultF, 1)
  })
})

describe('Array flattening', function() {
  it('must correctly flatten nested arrays', function() {
    const array1 = ['a', ['b', 'c'], 'd', 'e', [['f', 'g']]]
    const array2 = [1, 2, 3, 4]
    const array3 = []
    const array4 = [2, [4, [6, [8, [], [10]]]]]
    assert.deepStrictEqual(utils.array.flattenDeep(array1), [
      'a',
      'b',
      'c',
      'd',
      'e',
      'f',
      'g',
    ])
    assert.deepStrictEqual(utils.array.flattenDeep(array2), [1, 2, 3, 4])
    assert.deepStrictEqual(utils.array.flattenDeep(array3), [])
    assert.deepStrictEqual(utils.array.flattenDeep(array4), [2, 4, 6, 8, 10])
  })
})
