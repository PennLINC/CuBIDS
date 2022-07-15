const tagDelimiters = [',', '(', ')', '~']

/**
 * Split a HED string into delimiters and tags.
 *
 * @param {string} hedString The HED string to split.
 * @return {Array[]} A list of string parts. The boolean is true if the part is
 * a tag and false if it is a delimiter. The numbers are the bounds of the part.
 */
const splitHedString = function(hedString) {
  const resultPositions = []
  let currentSpacing = 0
  let insideDelimiter = true
  let startPosition = -1
  let lastEndPosition = 0

  for (let i = 0; i < hedString.length; i++) {
    const character = hedString.charAt(i)

    if (character === ' ') {
      currentSpacing++
      continue
    }

    if (tagDelimiters.includes(character)) {
      if (!insideDelimiter) {
        insideDelimiter = true
        if (startPosition >= 0) {
          lastEndPosition = i - currentSpacing
          resultPositions.push([true, [startPosition, lastEndPosition]])
          currentSpacing = 0
          startPosition = -1
        }
      }
      continue
    }

    if (insideDelimiter && lastEndPosition >= 0) {
      if (lastEndPosition !== i) {
        resultPositions.push([false, [lastEndPosition, i]])
      }
      lastEndPosition = -1
    }

    currentSpacing = 0
    insideDelimiter = false
    if (startPosition < 0) {
      startPosition = i
    }
  }

  if (lastEndPosition >= 0 && hedString.length !== lastEndPosition) {
    resultPositions.push([false, [lastEndPosition, hedString.length]])
  }

  if (startPosition >= 0) {
    resultPositions.push([
      true,
      [startPosition, hedString.length - currentSpacing],
    ])
    if (currentSpacing > 0) {
      resultPositions.push([
        false,
        [hedString.length - currentSpacing, hedString.length],
      ])
    }
  }

  return resultPositions
}

module.exports = splitHedString
