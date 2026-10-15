cmake_minimum_required(VERSION 3.16)
file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/src/version.h" _version_line REGEX "^#define PORT_VERSION")
string(REGEX MATCH "[0-9]+\\.[0-9]+(\\.[0-9]+)?" _port_version "${_version_line}")
project(AlfabetSmierci VERSION "${_port_version}" LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

find_package(PkgConfig REQUIRED)
pkg_check_modules(SDL3 REQUIRED IMPORTED_TARGET sdl3)
pkg_check_modules(OPENMPT REQUIRED IMPORTED_TARGET libopenmpt)

file(GLOB ENGINE_SOURCES CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/*.c")
if(APPLE)
    add_executable(alfabet_smierci MACOSX_BUNDLE ${ENGINE_SOURCES})
    set_target_properties(alfabet_smierci PROPERTIES
        OUTPUT_NAME "AlfabetSmierci"
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
        MACOSX_BUNDLE_BUNDLE_NAME "Alfabet Smierci"
        MACOSX_BUNDLE_GUI_IDENTIFIER "org.peteroman.alfabetsmierci"
        MACOSX_BUNDLE_BUNDLE_VERSION "${PROJECT_VERSION}"
        MACOSX_BUNDLE_SHORT_VERSION_STRING "${PROJECT_VERSION}")
    set(_resource_dir "$<TARGET_BUNDLE_DIR:alfabet_smierci>/Contents/Resources")
else()
    add_executable(alfabet_smierci ${ENGINE_SOURCES})
    set_target_properties(alfabet_smierci PROPERTIES
        OUTPUT_NAME "AlfabetSmierci"
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/AlfabetSmierci")
    set(_resource_dir "$<TARGET_FILE_DIR:alfabet_smierci>")
endif()

target_compile_options(alfabet_smierci PRIVATE -Wall -Wextra -Wno-unused-parameter)
target_compile_definitions(alfabet_smierci PRIVATE ALF_NATIVE_BUILD=1)
target_link_libraries(alfabet_smierci PRIVATE PkgConfig::SDL3 PkgConfig::OPENMPT)

# Keep runtime assets with the executable on Linux and in Resources for a macOS app bundle.
add_custom_target(alfabet_assets ALL
    COMMAND "${CMAKE_COMMAND}" -E copy_directory
        "${CMAKE_CURRENT_SOURCE_DIR}/AlfabetSmierci/data" "${_resource_dir}/data"
    COMMAND "${CMAKE_COMMAND}" -E copy_directory
        "${CMAKE_CURRENT_SOURCE_DIR}/scripts" "${_resource_dir}/data/scripts"
    VERBATIM)
add_dependencies(alfabet_assets alfabet_smierci)
