// This is the configuration schema for package

local moo = import "moo.jsonnet";
local sdc = import "daqconf/confgen.jsonnet";
local daqconf = moo.oschema.hier(sdc).dunedaq.daqconf.confgen;

local ns = "dunedaq.package.confgen";
local s = moo.oschema.schema(ns);

local cs = {

    int4 :    s.number(  "int4",    "i4",          doc="A signed integer of 4 bytes"),
    uint4 :   s.number(  "uint4",   "u4",          doc="An unsigned integer of 4 bytes"),
    int8 :    s.number(  "int8",    "i8",          doc="A signed integer of 8 bytes"),
    uint8 :   s.number(  "uint8",   "u8",          doc="An unsigned integer of 8 bytes"),
    float4 :  s.number(  "float4",  "f4",          doc="A float of 4 bytes"),
    double8 : s.number(  "double8", "f8",          doc="A double of 8 bytes"),
    boolean:  s.boolean( "Boolean",                doc="A boolean"),
    string:   s.string(  "String",   		   doc="A string"),   
    monitoring_dest: s.enum(     "MonitoringDest", ["local", "cern", "pocket"]),

    package: s.record("package", [
        s.field( "some_configured_value", self.int4, default=31415, doc="A value which configures the RenameMe DAQModule instance"),
        s.field( "num_renamemes", self.int4, default=1, doc="A value which configures the number of instances of RenameMe"),
    ]),

    package_gen: s.record("package_gen", [
        s.field("boot", daqconf.boot, default=daqconf.boot, doc="Boot parameters"),
        s.field("package", self.package, default=self.package, doc="package parameters"),
    ]),
};

// Output a topologically sorted array.
sdc + moo.oschema.sort_select(cs, ns)
