from medcat2.storage.serialisers import AvailableSerialisers


def get_test_classes():
    # NOTE: If these imports are at the top of the module
    #       the tests in the classes being imported would be
    #       ran again for the 2nd time in the context of this
    #       test module with the default parameters.
    #       That's because unittest would discover the classes
    #       present in the namespace.
    #       So by wrapping these in a method, we avoid that.
    from .test_serialisers import (
        SerialiserWorksTests, SerialiserFailsTests,
        NestedSameInstanceSerialisableTests,
        CanSerialiseCATSimple, CanSerialiseCATSlightlyComplex)

    class MsgPacksSerialiserWorksTests(SerialiserWorksTests):
        SERIALISER_TYPE = AvailableSerialisers.json

    class MsgPacksSerialiserFailsTests(SerialiserFailsTests):
        SERIALISER_TYPE = AvailableSerialisers.json

    class MsgPacksNestedSameInstanceSerialisableTests(
            NestedSameInstanceSerialisableTests):
        SERIALISER_TYPE = AvailableSerialisers.json

    class MsgPackCanSerialiseCAT(CanSerialiseCATSimple):
        SERIALSER_TYPE = AvailableSerialisers.json

    class MsgPackCanSerialiseCATSlightlyComplex(
        CanSerialiseCATSlightlyComplex
    ):
        SERIALISABLE_TYPE = AvailableSerialisers.json

    return (MsgPacksSerialiserWorksTests, MsgPacksSerialiserFailsTests,
            MsgPacksNestedSameInstanceSerialisableTests,
            MsgPackCanSerialiseCAT, MsgPackCanSerialiseCATSlightlyComplex)


# NOTE: by "dynamically" getting the classes, we avoid re-running
#       tests on the original classes.
CLS1, CLS2, CLS3, CLS4, CLS5 = get_test_classes()
