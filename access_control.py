import logging
log = logging.getLogger(__name__)

from utils import *

class ReadOnlyError(Exception):
    pass

# This can't defend against attacks against __dict__ or using del
# But it makes it harder, and makes a formal declaration on what's safe to change
# Also easier to catch cheaters
class ReadOnly(object):
    """Use _RO to set what values can't be changed."""
    def __setattr__(self, name, value):
        if name == "_RO":
            if name in self.__dict__ or name in self.__class__.__dict__:
                raise ReadOnlyError("Can't edit readonly attributes after creation")
        elif name in self._RO and name in self.__dict__ or name in self.__class__.__dict__:
            raise ReadOnlyError("Cannot edit " + name + " in " + str(self.__class__))
        super().__setattr__(name, value)

# Can set attributes, but only when _-preceded. Used to get protected style attributes
# Again, doesn't protect properly, but makes it harder to do / easier to detect
class Protected(object):
    def __setattr__(self, name, value):
        if name == "_PROT":
            if name in self.__dict__ or name in self.__class__.__dict__:
                raise ReadOnlyError("Can't edit protected attributes after creation")
        elif name in self._PROT:
            raise ReadOnlyError("Cannot edit " + name + " in " + str(self.__class__))
        elif name[0] == "_" and name[1:] in self._PROT:
            name = name[1:]
        super().__setattr__(name, value)


class Validity(object):
    @property
    def valid(self):
        if not "_valid" in self.__dict__:
            self._valid = True
        return self._valid
    @property
    def invalid(self):
        if not "_valid" in self.__dict__:
            self._valid = True
        return not self._valid
    def invalidate(self):
        self._valid = False


class PublicData(ReadOnly, Validity):
    def __init__(self, backer=None, for_=None):
        """If backer isn't set, must be init'd manually with set_data. Used to avoid dependency loops."""
        if backer is not None:
            self.set_data(backer, for_)
    def set_data(self, backer, for_):
        self._RO = tuple(backer._PUBLIC_ATTRS)
        for ro_val in self._RO:
            self.__setattr__(ro_val,
                public(getattr(backer, ro_val, None), for_))
        
class PrivateData(ReadOnly, Validity):
    def __init__(self, backer=None, for_=None):
        if backer is not None:
            self.set_data(backer, for_)
    def set_data(self, backer, for_):
        self._RO = tuple(backer._PRIVATE_ATTRS)
        for ro_val in self._RO:
            self.__setattr__(ro_val,
                private(getattr(backer, ro_val, None), for_))

class StaticPublicData(Protected, Validity):
    def __init__(self, backer=None, for_=None):
        if backer is not None:
            self.set_data(backer, for_)
    def set_data(self, backer, for_):
        self._PROT = tuple(backer._PUBLIC_ATTRS)
        for prot_val in self._PROT:
            self.__setattr__("_"+prot_val,
                public(getattr(backer, prot_val, None), for_))
        
class StaticPrivateData(Protected, Validity):
    def __init__(self, backer=None, for_=None):
        if backer is not None:
            self.set_data(backer, for_)
    def set_data(self, backer, for_):
        self._PROT = tuple(backer._PRIVATE_ATTRS)
        for prot_val in self._PROT:
            self.__setattr__("_"+prot_val,
                private(getattr(backer, prot_val, None), for_))





# Class to use Public data
# Overwrite PUBLIC_ATTRS each time, and PUBLIC_CLASS if needed
class PublicUser(object):
    _PUBLIC_ATTRS = ()
    _PUBLIC_CLASS = PublicData
    def _reset_public_info(self):
        self._public_for = {}
    def public_info(self, for_):
        if getattr(self, "_public_for", None) is None:
            self._reset_public_info()
        if not self._has_valid_pub(for_):
            # Use lazy init to avoid dependency loops
            self._public_for[for_] = self._PUBLIC_CLASS()
            self._public_for[for_].set_data(self, for_)
        return self._public_for[for_]
    def _has_valid_pub(self, for_):
        return for_ in self._public_for.keys() and self._public_for[for_].valid
    def invalidate_public(self, for_=ALL):
        for targ in self._public_for.keys():
            if for_ == ALL or targ in for_:
                self._public_for[targ].invalidate()

# Class to use Private data
# Overwrite PRIVATE_ATTRS each time, and PRIVATE_CLASS if needed
class PrivateUser(object):
    _PRIVATE_ATTRS = ()
    _PRIVATE_CLASS = PrivateData
    def _reset_private_info(self):
        self._private_for = {}
    def private_info(self, for_):
        if getattr(self, "_private_for", None) is None:
            self._reset_private_info()
        if not self._has_valid_priv(for_):
            # Use lazy init to avoid dependency loops
            self._private_for[for_] = self._PRIVATE_CLASS()
            self._private_for[for_].set_data(self, for_)
        return self._private_for[for_]
    def _has_valid_priv(self, for_):
        return for_ in self._private_for.keys() and self._private_for[for_].valid
    def invalidate_private(self, for_=ALL):
        for targ in self._private_for.keys():
            if for_ == ALL or targ in for_:
                self._private_for[targ].invalidate()
        



# Class to use static Public data
# Overwrite PUBLIC_ATTRS each time, and PUBLIC_CLASS if needed
# Will make sure that the Public data is always kept up to date
class StaticPublicUser(object):
    _PUBLIC_ATTRS = ()
    _PUBLIC_CLASS = StaticPublicData
    def _reset_public_info(self):
        self._public_for = {}
    def public_info(self, for_):
        if getattr(self, "_public_for", None) is None:
            self._reset_public_info()
        if not for_ in self._public_for.keys():
            # Use lazy init to avoid dependency loops
            self._public_for[for_] = self._PUBLIC_CLASS()
            self._public_for[for_].set_data(self, for_)
        return self._public_for[for_]
    def invalidate_public(self, for_=ALL):
        # Rather than invalidating the public data, we just 're-set' the relevant attributes
        # Due to the __setattr__ logic, this will update the data to be valid
        for attr in self._PUBLIC_ATTRS:
            setattr(self, attr, getattr(self, attr))
    def __setattr__(self, name, value):
        if name in self._PUBLIC_ATTRS and getattr(self, "_public_for", False):
            for for_, pubinfo in self._public_for.items():
                setattr(pubinfo, "_"+name, public(value, for_))
        super().__setattr__(name, value)


# Class to use static Private data
# Overwrite PRIVATE_ATTRS each time, and PRIVATE_CLASS if needed
# Will make sure that the Public data is always kept up to date
class StaticPrivateUser(object):
    _PRIVATE_ATTRS = ()
    _PRIVATE_CLASS = StaticPrivateData
    def _reset_private_info(self):
        self._private_for = {}
    def private_info(self, for_):
        if getattr(self, "_private_for", None) is None:
            self._reset_private_info()
        if not for_ in self._private_for.keys():
            # Use lazy init to avoid dependency loops
            self._private_for[for_] = self._PRIVATE_CLASS()
            self._private_for[for_].set_data(self, for_)
        return self._private_for[for_]
    def invalidate_private(self, for_=ALL):
        # Rather than invalidating the private data, we just 're-set' the relevant attributes
        # Due to the __setattr__ logic, this will update the data to be valid
        for attr in self._PRIVATE_ATTRS:
            setattr(self, attr, getattr(self, attr))
    def __setattr__(self, name, value):
        if name in self._PRIVATE_ATTRS and getattr(self, "_private_for", False):
            for for_, privinfo in self._private_for.items():
                setattr(privinfo, "_"+name, private(value, for_))
        super().__setattr__(name, value)



# Everything should use these functions to access public/private objects.
def public(obj, for_):
    # Need to convert to uid for the dicts
    log.debug("Public for: " + str(obj.__class__))
    uidfor_ = for_
    if getattr(for_, "type_", False) == PLAYER:
        uidfor_ = for_.uid
    try:
        return obj.public_info(uidfor_)
    except AttributeError as e:
        if isinstance(obj, (list,tuple)):
            return tuple([public(oo, uidfor_) for oo in obj])
        if isinstance(obj, dict):
            return {key: public(value, uidfor_) for key,value in obj.items()}
        # Would like to check some things to return None instead
        if not isinstance(obj, (str, int, None.__class__)):
            log.exception("Public issue:")
        return obj

def private(obj, for_):
    uidfor_ = for_
    if getattr(for_, "type_", False) == PLAYER:
        uidfor_ = for_.uid
    try:
        return obj.private_info(uidfor_)
    except AttributeError as e:
        if isinstance(obj, (list,tuple)):
            return tuple([private(oo, uidfor_) for oo in obj])
        if isinstance(obj, dict):
            return {key: private(value, uidfor_) for key,value in obj.items()}
        if not isinstance(obj, (str, int, None.__class__)):
            log.exception("Private issue:")
        return obj
