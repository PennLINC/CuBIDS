"""Miscellaneous utility functions for CuBIDS."""

import copy
import re
from pathlib import Path

from bids.layout import Query
from bids.utils import listify

from cubids.constants import FILE_COLLECTION_ENTITIES


def _get_container_type(image_name):
    """Get and return the container type.

    Parameters
    ----------
    image_name : :obj:`str`
        The name of the container image.

    Returns
    -------
    :obj:`str`
        The container type, either "docker" or "singularity".

    Raises
    ------
    :obj:`Exception`
        If the container type cannot be determined.
    """
    # If it's a file on disk, it must be a singularity image
    if Path(image_name).exists():
        return "singularity"

    # It needs to match a docker tag pattern to be docker
    if re.match(r"(?:.+\/)?([^:]+)(?::.+)?", image_name):
        return "docker"

    raise Exception("Unable to determine the container type of " + image_name)


def resolve_bids_uri(uri, root, dataset_links={}):
    """Resolve a BIDS URI to an absolute path.

    Parameters
    ----------
    uri : :obj:`str`
        The BIDS URI to resolve.
    root : :obj:`pathlib.Path`
        The root directory of the BIDS dataset.
    dataset_links : :obj:`dict`, optional
        A dictionary of dataset links.
        The keys are the names of the datasets,
        and the values are the paths to the root of the dataset.
        The paths can be either absolute or relative to the root of the current dataset.

    Returns
    -------
    :obj:`str`
        The absolute path to the file or directory specified by the URI.
    """
    if uri.startswith("bids::"):
        # This is a relative path from the root
        path = root / uri[6:]
    elif uri.startswith("bids:"):
        # More advanced BIDS URIs
        dataset_name, relative_path = uri[5:].split(":", 1)
        if dataset_name not in dataset_links:
            raise ValueError(f"Dataset '{dataset_name}' not found in dataset_links")

        dataset_link = dataset_links[dataset_name]
        if dataset_link.startswith("file://"):
            # Direct file link
            dataset_link = Path(dataset_link[7:])
        elif dataset_link.startswith("doi:"):
            # Remote link using a DOI
            raise NotImplementedError("doi URIs are not yet supported.")
        else:
            # Relative path from the root
            dataset_link = root / dataset_link

        path = dataset_link / relative_path

    return str(path.absolute())


def patch_collection_entities(entities):
    """Patch the entities of a collection.

    Parameters
    ----------
    entities : :obj:`dict`
        The entities of the collection.

    Returns
    -------
    :obj:`dict`
        The patched entities.
    """
    out_entities = copy.deepcopy(dict(entities))
    for entity in FILE_COLLECTION_ENTITIES:
        updated_values = listify(out_entities.get(entity, []))
        updated_values.append(Query.NONE)
        out_entities[entity] = updated_values

    return out_entities


def find_file(entities, layout):
    """Find a single file associated with the given entities."""
    file_candidates = layout.get(return_type="file", **entities)
    if len(file_candidates) > 1:
        file_str = "\n\t" + "\n\t".join(file_candidates)
        raise ValueError(f"Multiple associated files found:{file_str}")
    elif len(file_candidates) == 1:
        bvec_file = file_candidates[0]
        return bvec_file
    else:
        return None
