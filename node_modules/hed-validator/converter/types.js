/**
 * A tag dictionary entry.
 */
class TagEntry {
  /**
   * Constructor.
   * @param {string} shortTag The short version of the tag.
   * @param {string} longTag The long version of the tag.
   */
  constructor(shortTag, longTag) {
    /**
     * The short version of the tag.
     * @type {string}
     */
    this.shortTag = shortTag
    /**
     * The long version of the tag.
     * @type {string}
     */
    this.longTag = longTag
    /**
     * The formatted long version of the tag.
     * @type {string}
     */
    this.longFormattedTag = longTag.toLowerCase()
  }
}

/**
 * A short-to-long mapping.
 */
class Mapping {
  /**
   * Constructor.
   * @param {object<string, (TagEntry|TagEntry[])>} mappingData A dictionary mapping forms to TagEntry instances.
   * @param {boolean} hasNoDuplicates Whether the mapping has no duplicates.
   */
  constructor(mappingData, hasNoDuplicates) {
    /**
     * A dictionary mapping forms to TagEntry instances.
     * @type {Object<string, TagEntry|TagEntry[]>}
     */
    this.mappingData = mappingData
    /**
     * Whether the mapping has no duplicates.
     * @type {boolean}
     */
    this.hasNoDuplicates = hasNoDuplicates
  }
}

module.exports = {
  TagEntry: TagEntry,
  Mapping: Mapping,
}
