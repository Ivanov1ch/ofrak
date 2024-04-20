from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from ofrak.component.modifier import Modifier
from ofrak.model.component_model import ComponentConfig
from ofrak.model.resource_model import ResourceAttributes
from ofrak.resource import Resource
from ofrak_type.error import NotFoundError
from ofrak_type.range import Range


@dataclass(**ResourceAttributes.DATACLASS_PARAMS)
class CommentsAttributes(ResourceAttributes):
    """
    User-defined comments, list of the comments associated with an optional range.
    """

    comments: Dict[Optional[Range], List[str]]


@dataclass
class AddCommentModifierConfig(ComponentConfig):
    comment: Tuple[Optional[Range], str]


class AddCommentModifier(Modifier[AddCommentModifierConfig]):
    """
    Modifier to add a single comment to a resource.
    """

    targets = ()

    async def modify(self, resource: Resource, config: AddCommentModifierConfig) -> None:
        # Verify that the given range is valid for the given resource.
        config_range = config.comment[0]
        if config_range is not None:
            if config_range.start < 0 or config_range.end > len(await resource.get_data()):
                raise ValueError(
                    f"Range {config_range} is outside the bounds of "
                    f"resource {resource.get_id().hex()}"
                )
        try:
            # deepcopy the existing comments, otherwise they would be modified in place
            # and OFRAK would then compare the new attributes with the existing ones and find
            # they are the same, and report that the resource wasn't modified.
            comments = deepcopy(resource.get_attributes(CommentsAttributes).comments)
        except NotFoundError:
            comments = {}

        # Here I'm appending appending overlapping comments with a new line.
        # Overwriting comments that share a range is counter intuitive and not easily understood without digging into the code.
        if config.comment[0] not in comments:
            comments[config.comment[0]] = []

        comments[config.comment[0]].append(config.comment[1])
        resource.add_attributes(CommentsAttributes(comments=comments))


@dataclass
class DeleteCommentModifierConfig(ComponentConfig):
    """
    comment_range: Tuple[Optional[Range], comment_text=Optional[str]]
    If comment_text is provided, deletes the matching comment with the same Optional[Range]
    If comment_text is None, deletes ALL comments with the same Optional[Range]
    """

    comment_range: Tuple[Optional[Range], Optional[str]]

    def __post_init__(self):
        # Ensure there's always a two-element Tuple
        if type(self.comment_range) == tuple:
            # New format
            self.comment_range = (*self.comment_range, None)[:2]
        elif type(self.comment_range) == Range:
            # Old format: Range
            self.comment_range = (self.comment_range, None)
        else:
            # Old format: None (no Range provided)
            self.comment_range = (None, None)


class DeleteCommentModifier(Modifier[DeleteCommentModifierConfig]):
    """
    Modifier to delete a comment from a resource.
    """

    targets = ()

    async def modify(self, resource: Resource, config: DeleteCommentModifierConfig) -> None:
        """
        Delete the comment associated with the given range.

        :raises NotFoundError: if the comment range is not associated with a comment.
        """
        try:
            comments = deepcopy(resource.get_attributes(CommentsAttributes).comments)
        except NotFoundError:
            comments = {}
        try:
            if len(config.comment_range) == 1:
                config.comment_range = (config.comment_range[0], None)

            if config.comment_range[1] is None:
                del comments[config.comment_range[0]]
            else:
                comments[config.comment_range[0]].remove(config.comment_range[1])
                # Clean up if this was the last comment at this range
                if len(comments[config.comment_range[0]]) == 0:
                    del comments[config.comment_range[0]]
        except KeyError:
            raise NotFoundError(
                f"Comment range {config.comment_range[0]} not found in "
                f"resource {resource.get_id().hex()}"
            )
        except ValueError:
            raise NotFoundError(
                f"Comment {config.comment_range[1]} with range {config.comment_range[0]}"
                f" not found in resource {resource.get_id().hex()}"
            )
        resource.add_attributes(CommentsAttributes(comments=comments))
