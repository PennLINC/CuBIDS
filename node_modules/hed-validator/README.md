# hed-validator

This package contains a JavaScript validator for HED (hierarchical event descriptor) strings.

[HED](http://www.hedtags.org/) is a system for annotating events using comma-separated path strings. Any type of event can be annotated using HED-type syntax. The current version of `hed-validator` performs both syntactic and semantic validation. Syntactic validation only checks for syntactic issues like mismatched parentheses, and it does not require a schema.

The HED annotation strategy is very general and a standardized vocabulary for a particular domain can be represented using a HED schema. HED provides one [standardized schema](https://github.com/hed-standard/hed-specification) for annotating events in neuroimaging experiments. Validation of HED strings against a particular HED schema is called semantic validation. Semantic validation is currently supported for the [web version of the HED validator](http://visual.cs.utsa.edu/hed).

## Usage

To use the validator, follow these instructions:

1. Install the npm package `hed-validator`.
1. Add `const hedValidator = require('hed-validator')`.
1. (Semantic validation)
   1. Load a HED schema version using `hedValidator.validator.buildSchema()`. This returns a JavaScript `Promise` object. An optional object may be passed to `buildSchema()`. A `path` value is the path to a locally stored schema, while passing a `version` value will download that version. If no object or an empty object is passed, the latest version of the HED schema will be downloaded.
   1. Call the validator as follows (assuming `hedString` is the string to validate).
   ```javascript
   hedValidator.validator.buildSchema().then(hedSchema => {
     const [result, issues] = hedValidator.validator.validateHedString(
       hedString,
       hedSchema,
     )
   })
   ```
1. (Syntactic validation only) Call the validator as follows (assuming `hedString` is the string to validate). The second parameter is only required if checking for warnings.
   ```javascript
   const [result, issues] = hedValidator.validator.validateHedString(
     hedString,
     {},
   )
   ```

To check for warnings, pass `true` as the optional third argument.

## Examples

All of the examples assume that the `hed-validator` has been loaded:

```javascript
// For all examples
const hedValidator = require('hed-validator')
```

### Example 1: Calling `hed-validator` on a valid HED string

```javascript
// Initializing parameters and making the call
const validHedString =
  'Event/Category/Experimental stimulus,Item/Object/Vehicle/Train,Attribute/Visual/Color/Purple'
const [isValid1, issues1] = hedValidator.validator.validateHedString(
  validHedString,
)
```

After the call, the `isValid1` variable is `true` and `issues1` is empty.

### Example 2: Calling `hed-validator` when the HED string has a syntactic error (mismatched parentheses)

```javascript
// Initializing parameters and making the call
const invalidHedString2 =
  '/Action/Reach/To touch,((/Attribute/Object side/Left,/Participant/Effect/Body part/Arm),/Attribute/Location/Screen/Top/70 px'
const [isValid2, issues2] = hedValidator.validator.validateHedString(
  invalidHedString2,
)
```

After the call, `isValid2` is `false` and `issues2` has the value

```javascript
;[
  {
    code: 'parentheses',
    message:
      'ERROR: Number of opening and closing parentheses are unequal. 2 opening parentheses. 1 closing parentheses',
  },
]
```

### Example 3: Calling `hed-validator` when the HED string has a syntactic warning (bad capitalization), but no errors

```javascript
const warningHedString = 'Event/something'
const [isErrorFree, errorIssues] = hedValidator.validator.validateHedString(
  warningHedString,
)
const [isWarningFree, warningIssues] = hedValidator.validator.validateHedString(
  warningHedString,
  {},
  true,
)
```

After the calls, `isErrorFree` is `true` and `isWarningFree` is `false`. The `errorIssues` variable is empty, while the `warningIssues` variable contains

```javascript
;[
  {
    code: 'capitalization',
    message:
      'WARNING: First word not capitalized or camel case - "Event/something"',
  },
]
```

### Example 4: Calling `hed-validator` when the HED string has a semantic error (invalid tag)

```javascript
// Initialize parameter
const invalidHedString4 = 'Item/Nonsense'
// Build schema
hedValidator.validator.buildSchema().then(hedSchema => {
  // Validate
  const [isValid4, issues4] = hedValidator.validator.validateHedString(
    invalidHedString4,
    hedSchema,
  )
})
```

After the call, but inside the `then()` block, `isValid4` is `false` and `issues4` has the value

```javascript
;[
  {
    code: 'invalidTag',
    message: 'ERROR: Invalid tag - "Item/Nonsense"',
  },
]
```

### Example 5: Loading a non-default HED schema version

```javascript
const validHedString =
  'Event/Category/Experimental stimulus,Item/Object/Vehicle/Train,Attribute/Visual/Color/Purple'

// Load a remotely hosted schema version.
hedValidator.validator.buildSchema({ version: '7.0.4' }).then(hedSchema => {
  // Validate
  const [
    isValid5Remote,
    issues5Remote,
  ] = hedValidator.validator.validateHedString(validHedString, hedSchema)
  // Do something with results...
})

// Load a local schema file.
hedValidator.validator
  .buildSchema({ path: '/path/to/schema/file' })
  .then(hedSchema => {
    // Validate
    const [
      isValid5Local,
      issues5Local,
    ] = hedValidator.validator.validateHedString(validHedString, hedSchema)
    // Do something with results...
  })
```
