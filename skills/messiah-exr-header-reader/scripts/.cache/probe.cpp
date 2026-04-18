#include <iostream>
#include <string>
#include <OpenEXR/ImfInputFile.h>
#include <OpenEXR/ImfFloatAttribute.h>
#include <OpenEXR/ImfDoubleAttribute.h>
#include <OpenEXR/ImfIntAttribute.h>
#include <OpenEXR/ImfStringAttribute.h>
static bool readAttrAsDouble(const Imf::Header& header, const char* name, double& out){
  auto it = header.find(name);
  if(it==header.end()) return false;
  const Imf::Attribute& attr = it.attribute();
  std::string t = attr.typeName();
  if(t == Imf::FloatAttribute::staticTypeName()){ out = static_cast<const Imf::FloatAttribute&>(attr).value(); return true; }
  if(t == Imf::DoubleAttribute::staticTypeName()){ out = static_cast<const Imf::DoubleAttribute&>(attr).value(); return true; }
  if(t == Imf::IntAttribute::staticTypeName()){ out = static_cast<const Imf::IntAttribute&>(attr).value(); return true; }
  if(t == Imf::StringAttribute::staticTypeName()){ out = std::stod(static_cast<const Imf::StringAttribute&>(attr).value()); return true; }
  return false;
}
int main(int argc, char** argv){
  if(argc < 2){
    std::cerr << "need path\n";
    return 2;
  }
  try{
    Imf::InputFile f(argv[1]);
    const Imf::Header& h = f.header();
    double v = 0.0;
    if(readAttrAsDouble(h, "depth_flag", v)) std::cout << "depth_flag=" << v << "\n"; else std::cout << "depth_flag=<missing>\n";
    if(readAttrAsDouble(h, "MinDepth", v)) std::cout << "MinDepth=" << v << "\n"; else std::cout << "MinDepth=<missing>\n";
    if(readAttrAsDouble(h, "MaxDepth", v)) std::cout << "MaxDepth=" << v << "\n"; else std::cout << "MaxDepth=<missing>\n";
    if(readAttrAsDouble(h, "z_near", v)) std::cout << "z_near=" << v << "\n"; else std::cout << "z_near=<missing>\n";
    if(readAttrAsDouble(h, "z_far", v)) std::cout << "z_far=" << v << "\n"; else std::cout << "z_far=<missing>\n";
    return 0;
  }catch(const std::exception& e){
    std::cerr << "ERR " << e.what() << "\n";
    return 1;
  }
}
