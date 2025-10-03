# Kadoma: Control for Daikin BRC1H Thermostats

Kadoma is a Python library designed to provide control over the Daikin BRC1H family thermostats. It represents an alternative approach to the original [PyMadoka](https://github.com/mduran80/pymadoka/) project.

Original [README](README.pymadoka.md] included for reference.


## Why Kadoma? The rationale behind the fork and a rewrite

The journey to Kadoma started when attempting to integrate Daikin BRC1H units into [Home Assistant](https://www.home-assistant.io/). While existing efforts, such as the [daikin_madoka integration](https://github.com/mduran80/daikin_madoka), were noted, personal experience revealed persistent challenges and inconsistencies that hindered reliable operation.

Upon deeper investigation into the underlying pyMadoka library, it became apparent that, despite its functionality, the codebase presented significant obstacles to modification and enhancement. Its intricate structure impeded efficient bug resolution, feature implementation, and overall performance improvements.

After some refactoring and rewriting substantial portions of the original code, it became clear that a simple fork and subsequent pull request would not adequately convey the scope of the modifications. Consequently, the decision was made to rebrand this endeavor as Kadoma – a distinct, yet respectful, evolution of the core concepts, aimed at delivering a more maintainable, extensible, and user-friendly experience for controlling Daikin BRC1H devices.

Ultimately, Kadoma is intended to serve as a reliable and accessible tool for developers and users seeking to integrate their Daikin BRC1H thermostats into smart home ecosystems and custom applications.


## What provides Kadoma over pyMadoka

- Cleaner high-level interface (willing to improve)
- Simplier knobs (features in pyMadoka)
- Simplified transport (BLE protocol I/O)
- Some test units


## Has Kadoma additional features?

I tried to replicate the functionality of pyMadoka, but not as 1:1.

The command line utility, kadoma, has subcommands to control the Daikin units; mqtt interface and some raw BLE stuff.

Kadoma has the [Daikin BRC1H](https://github.com/ldotlopez/ha-daikin-brc1h/) Home Assistant integration as pyMadoka has the [daikin_madoka](https://github.com/mduran80/daikin_madoka) integration.
