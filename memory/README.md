# Thesis

## Generating the `.pdf`

To generate the `.pdf` from the `.tex` files, [download TeX Live]
and [follow the installation instructions]. In short, extract the
file and run the `install-tl` script:

```sh
wget http://mirror.ctan.org/systems/texlive/tlnet/install-tl-unx.tar.gz
tar xf install-tl-unx.tar.gz
install-tl-*/install-tl
```

Adding the chosen path to `/etc/environment` helped, but a reboot is needed.

It also seems to require Microsoft fonts (Times New Roman) to render properly.

## Template

The template for this memory can be found in the [Unex page for EPCC].

Note that the `.rar` is in fact a `.zip` file, and the contents use Windows
file endings, so those need to be converted with `dos2unix` or similar.

[download TeX Live]: https://www.tug.org/texlive/acquire-netinstall.html
[follow the installation instructions]: https://www.tug.org/texlive/quickinstall.html
[Unex page for EPCC]: https://www.unex.es/conoce-la-uex/centros/epcc/informacion-academica/tf-estudios/tfeg/plantillas
