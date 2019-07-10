# Licensed under a 3-clause BSD style license - see LICENSE.rst

import abc
import yaml
from functools import partial

from ..logger import logger, log_to_list
from ..py_utils import IndexedDict


# TODO: __str__, __repr__, print functions for all classes


__all__ = ['Config', 'Product', 'Instrument', 'Manager', 'Factory']


def info_dumper(infos):
    """Dump a dictionary information to a formated string.

    Now, it's just a wrapper to yaml.dump, put here to customize if needed.
    """
    return yaml.dump(infos)


class _GenericConfigClass(abc.ABC):
    """Class for generic sotring configs. Like a powered dict."""
    _frozen = False
    _prop_dict = IndexedDict()
    _mutable_vars = ['_frozen', 'logger']
    logger = logger

    def __init__(self, **kwargs):
        for name, value in kwargs.items():
            self.__setitem__(name, value)

    def __getattr__(self, name):
        if name in self._prop_dict.keys():
            return self.__getitem__(name)
        else:
            return super().__getattribute__(name)

    def __getitem__(self, name):
        if name in self._prop_dict:
            return self._prop_dict[name]
        else:
            # TODO: think if it is better to return None or raise error
            return None

    def __setattr__(self, name, value):
        if self._frozen:
            self.logger.warn('Tried to change `{}` with value `{}` while'
                             ' {} is frozen. Skipping.'
                             .format(name, value, self.__class__.__name__))
            return
        if name not in self.__class__.__dict__.keys():
            self.__setitem__(name, value)
        elif name in self._mutable_vars:
            # mutable vars
            super().__setattr__(name, value)
        else:
            raise KeyError('{} is a protected variable.'.format(name))

    def __setitem__(self, name, value):
        self._prop_dict[name] = value

    def __delattr__(self, name):
        if name in self._prop_dict.keys():
            del self._prop_dict[name]
        else:
            super().__delattr__(name)

    def __repr__(self):
        info = self.__class__.__name__ + "\n\n"
        info += info_dumper({'Properties': self.properties})
        return info

    def get(self, key, value):
        return self._prop_dict.get(key, value)

    def freeze(self):
        self._frozen = True

    def unfreeze(self):
        self._frozen = False

    @property
    def properties(self):
        return self._prop_dict.copy()

    @property
    def frozen(self):
        return self._frozen

    def update(self, config):
        for k, v in config.items():
            self.__setitem__(k, v)

    def items(self):
        return self._prop_dict.items()


class Config(_GenericConfigClass):
    """Store the config of a stage."""
    def __init__(self, *args, **kwargs):
        super(Config, self).__init__(*args, **kwargs)


class Instrument(_GenericConfigClass):
    """Store all the informations and needed functions of a instrument."""
    _frozen = False
    _prop_dict = {}
    _mutable_vars = ['_frozen']
    _identifier = 'dummy_instrument'

    def __init__(self, *args, **kwargs):
        super(Instrument, self).__init__(*args, **kwargs)

    def list_functions(self):
        """List the class functions."""
        # Pass any callable object that do not start with '_' may cause problem
        # This may pass unwanted functions. Commented out.
        # l = [i.__name__ for i in self.__class__.__dict__.values()
        #      if callable(i) and i.__name__[0] != '_']

        funcs = [i.__name__ for i in self.__class__.__dict__.values()
                 if type(i) in ['function', 'builtin_function_or_method'] and
                 i.__name__[0] != '_']

        # If needed to remove another class function, put here
        for i in ['list_functions']:
            if i in funcs:
                funcs.remove(i)
        return funcs

    def __str__(self):
        info = "{} ({})\n\n".format(self.__class__.__name__, self._identifier)
        info += info_dumper({'Properties': self.properties,
                             'Functions': self.list_functions()})
        return info

    def __repr__(self):
        return "{} ({})".format(self.__class__.__name__, self._identifier)


class Product():
    """Store all informations and data of a product."""
    _destruct_callbacks = []  # List of destruction callbacks
    _log_list = []  # Store the logs
    _variables = {}
    _infos = IndexedDict()
    _mutable_vars = ['_logger']  # Variables that can be assigned
    _instrument = None  # Product instrument
    _logger = None

    def __init__(self, manager=None, instrument=None, index=None,
                 **kwargs):
        if manager is None:
            raise ValueError("A product has to be created with a"
                             " manager.")
        # if not isinstance(product_manager, ProductManager):
        #     raise ValueError("product_manager is not a valid ProductManager "
        #                      "instance.")
        self._manager = manager
        self._instrument = instrument

        for name, value in kwargs.items():
            self.__setattr__(name, value)

    @property
    def index(self):
        return self._manager.get_product_index(self.name)

    @property
    def name(self):
        return self._manager.get_product_name(self)

    @property
    def logger(self):
        if self._logger is None:
            self._logger = self._manager.logger.getChild(self.name)
            log_to_list(self._logger, self._log_list)
        return self._logger

    @property
    def manager(self):
        return self._manager

    @property
    def capabilities(self):
        return self._capabilities

    @property
    def instrument(self):
        return self._instrument

    @property
    def info(self):
        """Print general informations about the product, in a yaml format."""
        info_dict = self._infos.copy()

        info_dict['variables'] = self._variables

        inst = dict()
        inst['class'] = self._instrument.__class__.__name__
        inst['id'] = self._instrument._identifier
        inst['properties'] = self._instrument.properties
        info_dict['instrument'] = inst

        dest = dict()
        dest['number'] = len(self._destruct_callbacks)
        dest['functions'] = [i.__name__ for i in self._destruct_callbacks]
        info_dict['destruction_callbacks'] = dest

        dest['history'] = self._log_list

        return info_dumper(info_dict)

    @property
    def log(self):
        """Print the log of the product."""
        return "\n".join(self._log_list)

    def get_value(self, name):
        """Get a variable value."""
        return self._variables[name]

    def set_value(self, name, value):
        """Set a value to a variable."""
        self._variables[name] = value

    def add_info(self, session, info_dict):
        """Custom add information dictionaries to the product."""
        if session in self._infos.keys():
            self.logger.warn('Session {} already exists in this product infos.'
                             ' Overwriting it.'
                             .format(session))
        if session in ['variables', 'history', 'destruction_callbacks']:
            self.logger.warn('{} is a protected name of session. Skipping.'
                             .format(session))
            return
        self._infos[session] = info_dict

    def add_destruct_callback(self, callback, *args, **kwargs):
        """Add a destruction callback. First argument must be a class slot,
        like self."""
        func = partial(callback, self, *args, **kwargs)
        self._destruct_callbacks.append(func)

    def destruct(self):
        """Execute the destruction callbacks sequentially."""
        for i, func in enumerate(self._destruct_callbacks):
            try:
                func()
            except Exception as e:
                logger.debug("Destruction callback {} problem. Error: {}"
                             .format(i, e))


class Stage(abc.ABC):
    """Stage process (sub-part) of a pipeline."""
    config = Config()  # stage default config
    name = None  # stage name
    _enabled = True  # stage enabled
    _requested_functions = []  # Instrument needed functions
    _requirements = []  # Product needed variables
    _provided = []  # Product variables provided by stage
    logger = logger

    def __init__(self, processor):
        self.processor = processor

    @property
    def enabled(self):
        return self._enabled

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    @abc.abstractmethod
    def run(self, product, config=None):
        """Run the stage"""

    def __call__(self, product, config=None):
        self.logger = product.logger
        self.run(product, config)


class Factory():
    _stages = IndexedDict()  # Stages list
    _register = IndexedDict()  # Variables registering
    _config = Config()
    _targets = []  # Stage targets for pipeline execution
    _active_product = None

    """Class to handle execution and product/stage interface."""


class Manager(abc.ABC):
    _config = Config()
    _products = IndexedDict()
    _factory = Factory()

    """Class to handle the general pipeline management."""
    def __init__(self, config_file=None):
        if config_file is not None:
            with open(config_file, 'r') as stream:
                self._config.update(yaml.load(stream))

    @abs.abstractmethod
    def setup_products(self, *args, **kwargs):
        """Setup products based on specified parameters.

        Examples:
            - Read files from a folder, with filters
            - List files
            - Load a configure file
        """

    def add_product(self, name, product, index=None, requires=[]):
        """Add a new product to this Manager.

        Parameters:
            name : string
                Indentifying name for this product. Uniqueness checked.
            product : `Product`
                Product valid instance.
            index : int
                Insert the product in a given index.
            requires : list(string)
                List of products to be processed first.
        """
        index1 = None
        try:
            inds = [self._products.index(r)
                    for r in requires]
            if len(inds) > 0:
                index1 = max(inds)

        if index1 is not None and index is not None:
            if index1 < index:
                logger.warn('Cannot insert product {} before its requirements.'
                            ' Overwriting to {}'.format(index, index1))
                index = index1

        if index is None:
            # If indexes are not set, just append
            self._products[name] = product
        else index is not None:
            self._products.insert_at(index, name, product)

    def get_product_index(self, name):
        """Return the current index of a given product."""
        for i, k in enumerate(self._products.keys()):
            if k == name:
                return i

        self.logger.warn("Product {} not found.".format(name))

    def get_product_name(self, instance):
        """Return the name of a product based on its instance."""
        for i, v in self._products.items():
            if v == instance:
                return i

        self.logger.warn("No product associated to {} instance."
                         .format(str(instance)))

    def del_product(self, name):
        """Remove and clean a product."""
        try:
            del self._products[name]
        except KeyError:
            logger.debug("Product {} not in this factory.".format(name))
            pass

    def register_stage(self, name, stage, disable_variables):
        """Register a stage"""

    def unregister_stage(sell, name):
        """Remove a stage from the registers."""

    def get_value(self, variable):
        """Get a value from a registered variable."""
        # If variable not set, run the responsible stage.
        # Check if the variable is running.

    def set_variable(self, stage, variable, value):
        """Set a variable value to product."""
        # Check if this stage can set the variable to product.
