from __future__ import absolute_import

import functools
import operator

from web3.iban import Iban

from web3.utils.string import (
    force_text,
    coerce_args_to_text,
    coerce_return_to_text,
)
from web3.utils.address import (
    is_address,
    is_strict_address,
    to_address,
)
from web3.utils.types import (
    is_array,
    is_string,
    is_null,
    is_object,
)
from web3.utils.formatting import (
    is_0x_prefixed,
    add_0x_prefix,
)
from web3.utils.encoding import (
    to_hex,
    encode_hex,
    decode_hex,
    from_decimal,
    to_decimal,
)
from web3.utils.functional import (
    identity,
    compose,
)


def apply_if_passes_test(test_fn):
    def outer_fn(fn):
        @functools.wraps(fn)
        def inner(value):
            if test_fn(value):
                return fn(value)
            return value
        return inner
    return outer_fn


apply_if_not_null = apply_if_passes_test(compose(is_null, operator.not_))
apply_if_string = apply_if_passes_test(is_string)
apply_if_array = apply_if_passes_test(is_array)


def isPredefinedBlockNumber(blockNumber):
    if not is_string(blockNumber):
        return False
    return force_text(blockNumber) in {"latest", "pending", "earliest"}


def inputBlockNumberFormatter(blockNumber):
    if not blockNumber:
        return None
    elif isPredefinedBlockNumber(blockNumber):
        return blockNumber
    return to_hex(blockNumber)


@coerce_args_to_text
@coerce_return_to_text
def input_call_formatter(eth, txn):
    defaults = {
        'from': eth.defaultAccount,
    }
    formatters = {
        'from': input_address_formatter,
        'to': input_address_formatter,
    }
    return {
        key: formatters.get(key, identity)(txn.get(key, defaults.get(key)))
        for key in set(tuple(txn.keys()) + tuple(defaults.keys()))
    }


@coerce_args_to_text
@coerce_return_to_text
def input_transaction_formatter(eth, txn):
    defaults = {
        'from': eth.defaultAccount,
    }
    formatters = {
        'from': input_address_formatter,
        'to': input_address_formatter,
    }
    return {
        key: formatters.get(key, identity)(txn.get(key, defaults.get(key)))
        for key in set(tuple(txn.keys()) + tuple(defaults.keys()))
    }


@coerce_args_to_text
@coerce_return_to_text
def output_transaction_formatter(txn):
    formatters = {
        'blockNumber': apply_if_not_null(to_decimal),
        'transactionIndex': apply_if_not_null(to_decimal),
        'nonce': to_decimal,
        'gas': to_decimal,
        'gasPrice': to_decimal,
        'value': to_decimal,
    }

    return {
        key: formatters.get(key, identity)(value)
        for key, value in txn.items()
    }


@coerce_return_to_text
def output_log_formatter(log):
    """
    Formats the output of a log
    """
    formatters = {
        'blockNumber': apply_if_not_null(to_decimal),
        'transactionIndex': apply_if_not_null(to_decimal),
        'logIndex': apply_if_not_null(to_decimal),
        'address': to_address,
    }

    return {
        key: formatters.get(key, identity)(value)
        for key, value in log.items()
    }


log_array_formatter = apply_if_not_null(compose(
    functools.partial(map, output_log_formatter),
    list,
))


apply_if_array_of_dicts = apply_if_passes_test(compose(
    functools.partial(map, is_object),
    all,
))


@coerce_args_to_text
@coerce_return_to_text
def output_transaction_receipt_formatter(receipt):
    """
    Formats the output of a transaction receipt to its proper values
    """
    if receipt is None:
        return None

    formatters = {
        'blockNumber': to_decimal,
        'transactionIndex': to_decimal,
        'cumulativeGasUsed': to_decimal,
        'gasUsed': to_decimal,
        'logs': apply_if_array_of_dicts(log_array_formatter),
    }

    return {
        key: formatters.get(key, identity)(value)
        for key, value in receipt.items()
    }


@coerce_return_to_text
def output_block_formatter(block):
    """
    Formats the output of a block to its proper values
    """
    formatters = {
        'gasLimit': to_decimal,
        'gasUsed': to_decimal,
        'size': to_decimal,
        'timestamp': to_decimal,
        'number': apply_if_not_null(to_decimal),
        'difficulty': to_decimal,
        'totalDifficulty': to_decimal,
        'transactions': apply_if_array(
            functools.partial(map, apply_if_string(output_transaction_formatter)),
        )
    }

    return {
        key: formatters.get(key, identity)(value)
        for key, value in block.items()
    }


filter_output_formatter = apply_if_array_of_dicts(log_array_formatter)


@coerce_return_to_text
def inputPostFormatter(post):
    """
    Formats the input of a whisper post and converts all values to HEX
    """

    post["ttl"] = from_decimal(post["ttl"])
    post["workToProve"] = from_decimal(post.get("workToProve", 0))
    post["priority"] = from_decimal(post["priority"])

    if not is_array(post.get("topics")):
        post["topics"] = [post["topics"]] if post.get("topics") else []

    post["topics"] = [topic if is_0x_prefixed(topic) else encode_hex(topic)
                      for topic in post["topics"]]

    return post


@coerce_return_to_text
def outputPostFormatter(post):
    """
    Formats the output of a received post message
    """

    post["expiry"] = to_decimal(post["expiry"])
    post["sent"] = to_decimal(post["sent"])
    post["ttl"] = to_decimal(post["ttl"])
    post["workProved"] = to_decimal(post["workProved"])

    if not post.get("topics"):
        post["topics"] = []

    post["topics"] = [decode_hex(topic) for topic in post["topics"]]

    return post


def input_address_formatter(addr):
    iban = Iban(addr)
    if iban.isValid() and iban.isDirect():
        return add_0x_prefix(iban.address())
    elif is_strict_address(addr):
        return addr
    elif is_address(addr):
        return add_0x_prefix(addr)

    raise ValueError("invalid address")


def outputSyncingFormatter(result):
    result["startingBlock"] = to_decimal(result["startingBlock"])
    result["currentBlock"] = to_decimal(result["currentBlock"])
    result["highestBlock"] = to_decimal(result["highestBlock"])

    return result


def transaction_pool_formatter(value, txn_formatter):
    return {
        'pending': {
            sender: {
                to_decimal(nonce): [txn_formatter(txn) for txn in txns]
                for nonce, txns in txns_by_sender.items()
            } for sender, txns_by_sender in value.get('pending', {}).items()
        },
        'queued': {
            sender: {
                to_decimal(nonce): [txn_formatter(txn) for txn in txns]
                for nonce, txns in txns_by_sender.items()
            } for sender, txns_by_sender in value.get('queued', {}).items()
        },
    }


def transaction_pool_content_formatter(value):
    return transaction_pool_formatter(value, output_transaction_formatter)


def transaction_pool_inspect_formatter(value):
    return transaction_pool_formatter(value, identity)


def syncing_formatter(value):
    if not value:
        return value

    formatters = {
        'startingBlock': to_decimal,
        'currentBlock': to_decimal,
        'highestBlock': to_decimal,
    }

    return {
        key: formatters.get(key, identity)(value)
        for key, value in value.items()
    }
