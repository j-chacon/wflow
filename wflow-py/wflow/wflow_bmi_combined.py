
import wflow.bmi as bmi
import wflow.wflow_bmi as wfbmi
import wflow
import os
from wflow.pcrut import setlogger
from wflow.wflow_lib import configget
import ConfigParser


def iniFileSetUp(configfile):
    """
    Reads .ini file and returns a config object.


    """
    config = ConfigParser.SafeConfigParser()
    config.optionxform = str
    config.read(configfile)
    return config


def configsection(config,section):
    """
    gets the list of lesy in a section

    Input:
        - config
        - section

    Output:
        - list of keys in the section
    """
    try:
        ret = config.options(section)
    except:
        ret = []

    return ret

class wflowbmi_csdms(bmi.Bmi):
    """
    csdms BMI implementation runner for combined pcraster/python models


    + all variables are identified by: component_name/variable_name
    + this version is specific for a routing component combined by land surface component.
    + get_component_name returns a comm separated list of components

    """

    def __init__(self):
        """
        Initialises the object

        :return: nothing
        """

        self.bmimodels = {}
        self.currenttimestep = 0
        self.exchanges = []

    def __getmodulenamefromvar__(self,long_var_name):
        """

        :param long_var_name:
        :return: name of the module
        """
        return long_var_name.split('/')[0]

    def initialize_config(self, filename):
        """
        *Extended functionality*, see https://github.com/eWaterCycle/bmi/blob/master/src/main/python/bmi.py

        see initialize

        :param filename:
        :param loglevel:
        :return: nothing
        """

        self.currenttimestep = 1

        self.config = iniFileSetUp(filename)
        self.datadir = os.path.dirname(filename)
        inifile = os.path.basename(filename)

        self.models = configsection(self.config,'models')
        self.exchanges= configsection(self.config,'exchanges')

        for mod in self.models:
            self.bmimodels[mod] = wfbmi.wflowbmi_csdms()

        # Initialize all bmi model objects
        for key, value in self.bmimodels.iteritems():
            modconf = self.config.get('models',key)
            self.bmimodels[key].initialize_config(modconf)



    def initialize_model(self):
        """
        *Extended functionality*, see https://github.com/eWaterCycle/bmi/blob/master/src/main/python/bmi.py

        see initialize

        :param self:
        :return: nothing
        """

        for key, value in self.bmimodels.iteritems():
            self.bmimodels[key].initialize_model()

        # Copy and set the variables to be exchanged for step 0
        for key, value in self.bmimodels.iteritems():
            # step one update first model
            curmodel = self.bmimodels[key].get_component_name()
            for item in self.exchanges:
                supplymodel = self.__getmodulenamefromvar__(item)
                if curmodel == supplymodel:
                    outofmodel = self.get_value(item)
                    tomodel = self.config.get('exchanges',item)
                    self.set_value(tomodel,outofmodel)



    def set_start_time(self, start_time):
        """

        :param start_time: time in units (seconds) since the epoch
        :return: nothing
        """
        for key, value in self.bmimodels.iteritems():
            self.bmimodels[key].set_start_time(start_time)

    def set_end_time(self, end_time):
        """
        :param end_time: time in units (seconds) since the epoch
        :return:
        """
        for key, value in self.bmimodels.iteritems():
            self.bmimodels[key].set_send_time(end_time)



    def get_attribute_names(self):
        """
        Get the attributes of the model return in the form of section_name:attribute_name

        :return: list of attributes
        """
        names = []
        for key, value in self.bmimodels.iteritems():
            names.append(self.bmimodels[key].get_attribute_names())
            names[-1] = [self.bmimodels[key].get_component_name() + "/" + s for s in names[-1]]

        ret = [item for sublist in names for item in sublist]
        return ret

    def get_attribute_value(self, attribute_name):
        """
        :param attribute_name:
        :return: attribute value
        """
        cname = attribute_name.split('/')
        return self.bmimodels[cname[0]].get_attribute_value(cname[1])


    def set_attribute_value(self, attribute_name, attribute_value):
        """
        :param attribute_name: name using the section:option notation
        :param attribute_value: string value of the option
        :return:
        """
        cname = attribute_name.split('/')
        self.bmimodels[cname[0]].set_attribute_value(cname[1],attribute_value)


    def initialize(self, filename):
        """
        Initialise the model. Should be called before any other method.

        :var filename: full path to the wflow ini file
        :var loglevel: optional loglevel (default == DEBUG)

        Assumptions for now:

            - the configfile wih be a full path
            - we define the case from the basedir of the configfile

        """

        self.initialize_config(filename)
        self.initialize_model()



    def update(self):
        """
        Propagate the model to the next model timestep
        """
        for key, value in self.bmimodels.iteritems():
            # step one update first model
            self.bmimodels[key].update()
            # do all exchanges
            curmodel = self.bmimodels[key].get_component_name()
            for item in self.exchanges:
                supplymodel = self.__getmodulenamefromvar__(item)
                if curmodel == supplymodel:
                    outofmodel = self.get_value(item)
                    tomodel = self.config.get('exchanges',item)
                    self.set_value(tomodel,outofmodel)

        self.currenttimestep = self.currenttimestep + 1

    def update_until(self, time):
        """
        Update the model until and including the given time.

        - one or more timesteps foreward
        - max one timestep backward

        :var  double time: time in the units and epoch returned by the function get_time_units.
        """
        curtime = self.get_current_time()

        if abs(time - curtime)% self.get_time_step() != 0:
            raise ValueError("Update in time not a multiple of timestep")

        if curtime > time:
            timespan = curtime - time
            nrstepsback = int(timespan/self.get_time_step())
            if nrstepsback > 1:
                raise ValueError("Time more than one timestep before current time.")
            for key, value in self.bmimodels.iteritems():
                self.bmimodels[key].dynModel.wf_QuickResume()

        else:
            timespan = time - curtime
            nrsteps = int(timespan/self.get_time_step())

            #self.dynModel._runDynamic(self.currenttimestep, self.currenttimestep + nrsteps -1)
            for st in range(0,nrsteps):
                #for key, value in self.bmimodels.iteritems():
                self.update()

            #self.currenttimestep = self.currenttimestep + nrsteps

    def update_frac(self, time_frac):
        """
        Not implemented. Raises a NotImplementedError
        """
        raise NotImplementedError

    def save_state(self, destination_directory):
        """
        Ask the model to write its complete internal current state to one or more state files in the given directory.
        Afterwards the given directory will only contain the state files and nothing else.
        Sates are save in the models' native format.

        :var destination_directory: the directory in which the state files should be written.
        """
        for key, value in self.bmimodels.iteritems():
            self.bmimodels[key].save_state(destination_directory)


    def load_state(self, source_directory):
        """
        Ask the model to load its complete internal current state from one or more
        state files in the given directory.

        :var  source_directory: the directory from which the state files should be
        read.
        """
        for key, value in self.bmimodels.iteritems():
            self.bmimodels[key].save_state(source_directory)

    def finalize(self):
        """
        Shutdown the library and clean up the model.
        Uses the default (model configured) state location to also save states.
        """
        for key, value in self.bmimodels.iteritems():
            self.bmimodels[key].finalize()

    def get_component_name(self):
        """
        :return:  identifier of the models separated by a comma (,)
        """
        names = []
        for key, value in self.bmimodels.iteritems():
            names.append(self.bmimodels[key].get_component_name())

        return ",".join(names)


    def get_input_var_names(self):
        """

        :return: List of String objects: identifiers of all input variables of the model:
        """
        names = []
        for key, value in self.bmimodels.iteritems():
            names.append(self.bmimodels[key].get_input_var_names())
            names[-1] = [self.bmimodels[key].get_component_name() + "/" + s for s in names[-1]]

        ret = [item for sublist in names for item in sublist]
        return ret

    def get_output_var_names(self):
        """
        Returns the list of model output variables

        :return: List of String objects: identifiers of all output variables of the model:
        """
        names = []
        for key, value in self.bmimodels.iteritems():
            names.append(self.bmimodels[key].get_output_var_names())
            names[-1] = [self.bmimodels[key].get_component_name() + "/" + s for s in names[-1]]

        ret = [item for sublist in names for item in sublist]

        return ret

    def get_var_type(self, long_var_name):
        """
        Gets the variable type as a numpy type string

        :return: variable type string, compatible with numpy:
        """

        # first part should be the component name
        cname = long_var_name.split('/')
        for key, value in self.bmimodels.iteritems():
            nn = self.bmimodels[key].get_component_name()
            if nn == cname[0]:
                ret = self.bmimodels[key].get_var_type(cname[1])

        return ret

    def get_var_rank(self, long_var_name):
        """
        Gets the number of dimensions for a variable

        :var  String long_var_name: identifier of a variable in the model:
        :return: array rank or 0 for scalar (number of dimensions):
        """
        # first part should be the component name
        cname = long_var_name.split('/')
        for key, value in self.bmimodels.iteritems():
            nn = self.bmimodels[key].get_component_name()
            if nn == cname[0]:
                ret = self.bmimodels[key].get_var_rank(cname[1])

        return ret


    def get_var_size(self, long_var_name):
        """
        Gets the number of elements in a variable (rows * cols)

        :var  String long_var_name: identifier of a variable in the model:
        :return: total number of values contained in the given variable (number of elements in map)
        """
        # first part should be the component name
        cname = long_var_name.split('/')
        for key, value in self.bmimodels.iteritems():
            nn = self.bmimodels[key].get_component_name()
            if nn == cname[0]:
                ret = self.bmimodels[key].get_var_size(cname[1])

        return ret

    def get_var_nbytes(self, long_var_name):
        """
        Gets the number of bytes occupied in memory for a given variable.

        :var  String long_var_name: identifier of a variable in the model:
        :return: total number of bytes contained in the given variable (number of elements * bytes per element)
        """
        # first part should be the component name
        cname = long_var_name.split('/')
        for key, value in self.bmimodels.iteritems():
            nn = self.bmimodels[key].get_component_name()
            if nn == cname[0]:
                ret = self.bmimodels[key].get_var_nbytes(cname[1])

        return ret

    def get_start_time(self):
        """
        Gets the start time of the model.

        :return: start time of last model in the list. Tiem sare assumed to be identical
        """
        st = []
        for key, value in self.bmimodels.iteritems():
            st.append(self.bmimodels[key].get_start_time())

        return st[-1]

    def get_current_time(self):
        """
        Get the current time since the epoch of the model

        :return: current time of simulation n the units and epoch returned by the function get_time_units
        """

        st = []
        for key, value in self.bmimodels.iteritems():
            st.append(self.bmimodels[key].get_current_time())

        return st[-1]

    def get_end_time(self):
        """
        Get the end time of the model run in units since the epoch

        :return: end time of simulation n the units and epoch returned by the function get_time_units
        """
        st = []
        for key, value in self.bmimodels.iteritems():
            st.append(self.bmimodels[key].get_end_time())

        return st[-1]

    def get_time_step(self):
        """
        Get the model time steps in units since the epoch

        :return: duration of one time step of the model with the largest! timestep.
        """
        st = []
        for key, value in self.bmimodels.iteritems():
            st.append(self.bmimodels[key].get_time_step())

        return max(st)

    def get_time_units(self):
        """
        Return the time units of the model as a string

        :return: Return a string formatted using the UDUNITS standard from Unidata.
        (http://cfconventions.org/Data/cf-conventions/cf-conventions-1.7/build/cf-conventions.html#time-coordinate)
        """
        st = []
        for key, value in self.bmimodels.iteritems():
            st.append(self.bmimodels[key].get_time_units())

        return st[-1]



    def get_value(self, long_var_name):
        """
        Get the value(s) of a variable as a numpy array

        :var long_var_name: name of the variable
        :return: a np array of long_var_name
        """
        # first part should be the component name
        cname = long_var_name.split('/')
        if self.bmimodels.has_key(cname[0]):
            return self.bmimodels[cname[0]].get_value(cname[1])
        else:
            return None


    def get_value_at_indices(self, long_var_name, inds):
        """
        Get a numpy array of the values at the given indices

        :var long_var_name: identifier of a variable in the model:
        :var inds: List of list each tuple contains one index for each dimension of the given variable, i.e. each tuple indicates one element in the multi-dimensional variable array:

        :return: numpy array of values in the data type returned by the function get_var_type.
        """
        cname = long_var_name.split('/')

        if self.bmimodels.has_key(cname[0]):
            return self.bmimodels[cname[0]].get_value_at_indices(cname[1],inds)
        else:
            return None


    def set_value_at_indices(self, long_var_name, inds, src):
        """
        Set the values in a variable using a numpy array of the values given indices

        :var long_var_name: identifier of a variable in the model:
        :var inds: List of Lists of integers inds each nested List contains one index for each dimension of the given variable,
                                        i.e. each nested List indicates one element in the multi-dimensional variable array,
                                        e.g. [[0, 0], [0, 1], [15, 19], [15, 20], [15, 21]] indicates 5 elements in a 2D grid.:
        :var src: Numpy array of values. one value to set for each of the indicated elements:
        """
        cname = long_var_name.split('/')
        if self.bmimodels.has_key(cname[0]):
            self.bmimodels[cname[0]].set_value_at_indices(cname[1], inds,src)


    def get_grid_type(self, long_var_name):
        """
        Get the grid type according to the enumeration in BmiGridType

        :var String long_var_name: identifier of a variable in the model.

        :return: BmiGridType type of the grid geometry of the given variable.
        """
        cname = long_var_name.split('/')

        if self.bmimodels.has_key(cname[0]):
            return self.bmimodels[cname[0]].get_grid_type(cname[1])
        else:
            return None

    def get_grid_shape(self, long_var_name):
        """
        Return the shape of the grid. Only return something for variables with a uniform, rectilinear or structured grid. Otherwise raise ValueError.

        :var long_var_name: identifier of a variable in the model.

        :return: List of integers: the sizes of the dimensions of the given variable, e.g. [500, 400] for a 2D grid with 500x400 grid cells.
        """
        cname = long_var_name.split('/')

        if self.bmimodels.has_key(cname[0]):
            return self.bmimodels[cname[0]].get_grid_shape(cname[1])
        else:
            return None


    def get_grid_spacing(self, long_var_name):
        """
        Only return something for variables with a uniform grid. Otherwise raise ValueError.

        :var long_var_name: identifier of a variable in the model.

        :return: The size of a grid cell for each of the dimensions of the given variable, e.g. [width, height]: for a 2D grid cell.
        """
        cname = long_var_name.split('/')

        if self.bmimodels.has_key(cname[0]):
            return self.bmimodels[cname[0]].get_grid_spacing(cname[1])
        else:
            return None


    def get_grid_origin(self, long_var_name):
        """
        gets the origin of the model grid.

        :var String long_var_name: identifier of a variable in the model.

        :return: X, Y: ,the lower left corner of the grid.
        """
        cname = long_var_name.split('/')

        if self.bmimodels.has_key(cname[0]):
            return self.bmimodels[cname[0]].get_grid_origin(cname[1])
        else:
            return None


    def get_grid_x(self, long_var_name):
        """
        Give X coordinates of point in the model grid

        :var String long_var_name: identifier of a variable in the model.

        :return: Numpy array of doubles: x coordinate of grid cell center for each grid cell, in the same order as the
        values returned by function get_value.
        """
        cname = long_var_name.split('/')

        if self.bmimodels.has_key(cname[0]):
            return self.bmimodels[cname[0]].get_grid_x(cname[1])
        else:
            return None


    def get_grid_y(self, long_var_name):
        """
        Give Y coordinates of point in the model grid

        :var String long_var_name: identifier of a variable in the model.

        :return: Numpy array of doubles: y coordinate of grid cell center for each grid cell, in the same order as the
        values returned by function get_value.

        """
        cname = long_var_name.split('/')

        if self.bmimodels.has_key(cname[0]):
            return self.bmimodels[cname[0]].get_grid_y(cname[1])
        else:
            return None

    def get_grid_z(self, long_var_name):
        """
        Give Z coordinates of point in the model grid

        :var String long_var_name: identifier of a variable in the model.

        :return: Numpy array of doubles: z coordinate of grid cell center for each grid cell, in the same order as the values returned by function get_value.
        """
        cname = long_var_name.split('/')

        if self.bmimodels.has_key(cname[0]):
            return self.bmimodels[cname[0]].get_grid_z(cname[1])
        else:
            return None


    def get_var_units(self, long_var_name):
        """
        Supply units as defined in the API section of the ini file

        :var long_var_name: identifier of a variable in the model.

        :return:   String: unit of the values of the given variable. Return a string formatted
        using the UDUNITS standard from Unidata. (only if set properly in the ini file)
        """

        cname = long_var_name.split('/')

        if self.bmimodels.has_key(cname[0]):
            return self.bmimodels[cname[0]].get_var_units(cname[1])
        else:
            return None

    def set_value(self, long_var_name, src):
        """
        Set the values(s) in a map using a numpy array as source

        :var long_var_name: identifier of a variable in the model.
        :var src: all values to set for the given variable. If only one value
                  is present a uniform map will be set in the wflow model.
        """
        # first part should be the component name
        cname = long_var_name.split('/')
        if self.bmimodels.has_key(cname[0]):
            self.bmimodels[cname[0]].set_value(cname[1],src)



    def get_grid_connectivity(self, long_var_name):
        """
        Not applicable, raises NotImplementedError
        Should return the ldd if present!!
        """
        raise NotImplementedError

    def get_grid_offset(self, long_var_name):
        """
        Not applicable raises NotImplementedError
        """
        raise NotImplementedError
