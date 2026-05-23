from medcat.tokenizing.tokenizers import MutableDocument, MutableEntity, MutableToken
from medcat.config.config import Config
from medcat_rawstring_tokenizer.tokens import Token, Entity, Document
from typing import Type

class RawstringTokenizer:
    """The base tokenizer protocol."""
    
    def __init__(self, config: Config):
        self.config = config
        pass

    def create_entity(self, doc: MutableDocument,
                      token_start_index: int, token_end_index: int,
                      label: str) -> MutableEntity:
        """Create an entity from a document.

        Args:
            doc (MutableDocument): The document to use.
            token_start_index (int): The token start index.
            token_end_index (int): The token end index.
            label (str): The detected name for the entity.

        Returns:
            MutableEntity: The resulting entity.
        """
        # Get tokens to determine character span and text
        tokens = doc[token_start_index:token_end_index]
        if not tokens:
            raise ValueError("No tokens in the specified range")
        # Construct entity text and determine character span
        text = " ".join(tkn.text for tkn in tokens)
        start_char = tokens[0].char_index
        end_char = tokens[-1].end_char_index
        # TODO: Check this is the correct length
        # maybe + 1
        text = doc.text[start_char:end_char]
        # Create entity with both token and character spans
        entity = Entity(text, token_start_index, token_end_index, start_char, end_char, label)
        return entity

    def entity_from_tokens(self, tokens: list[MutableToken]) -> MutableEntity:
        """Get an entity from the list of tokens.

        This will create a new instance instead of looking for existing entity.
        This method should be used only if/when there was no existing entity
        within the specified document for the given span of tokens.

        Args:
            tokens (list[MutableToken]): List of tokens.

        Returns:
            MutableEntity: The resulting entity.
        """
        if not tokens:
            raise ValueError("Need at least one token for an entity")
        text = " ".join(tkn.text for tkn in tokens)
        start_index = tokens[0].index
        end_index = tokens[-1].index + 1
        start_char = tokens[0].char_index
        end_char = tokens[-1].end_char_index
        # Entity uses [start, end] char semantics, so end must stay exclusive.
        return Entity(text, start_index, end_index, start_char, end_char, text)
        

    def entity_from_tokens_in_doc(self, tokens: list[MutableToken],
                                  doc: MutableDocument) -> MutableEntity:
        """Get an entity from the list of tokens in the specified document.

        This method is designed to reuse entities where possible.
        I don't think the document is required for this implementation.

        Args:
            tokens (list[MutableToken]): List of tokens.
            doc (MutableDocument): The document for these tokens.

        Returns:
            MutableEntity: The resulting entity.
        """
        return self.entity_from_tokens(tokens)

    def __call__(self, text: str) -> MutableDocument:
        doc = Document(text)
        return doc

    @classmethod
    def create_new_tokenizer(cls, config: Config) -> 'RawstringTokenizer':
        return cls(config)

    def get_doc_class(self) -> Type[MutableDocument]:
        """Get the document implementation class used by the tokenizer.

        This can be used (e.g) to register addon paths.

        Returns:
            Type[MutableDocument]: The document class.
        """
        return Document

    def get_entity_class(self) -> Type[MutableEntity]:
        """Get the entity implementation class used by the tokenizer.

        Returns:
            Type[MutableEntity]: The entity class.
        """
        return Entity

