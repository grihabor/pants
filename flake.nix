{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    rust-overlay.url = "github:oxalica/rust-overlay";
  };

  outputs = {
    self,
    nixpkgs,
    rust-overlay,
  }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs {
      inherit system;
      overlays = [
        rust-overlay.overlays.default
        (import ./nix/hatchling.nix)
      ];
    };
    lib = nixpkgs.lib;
    rust-toolchain = builtins.fromTOML (builtins.readFile ./src/rust/engine/rust-toolchain);
    rustVersion = rust-toolchain.toolchain.channel;
    pants-bin = pkgs.callPackage ./pants.nix {
      cargo = pkgs.rust-bin.stable.${rustVersion}.default;
      rustc = pkgs.rust-bin.stable.${rustVersion}.default;
    };
  in {
    packages.${system}.default = pants-bin;
    devShells.${system}.default = pkgs.mkShell rec {
      packages = [
        pants-bin
        pkgs.python3Packages.fastapi
        pkgs.python3Packages.strawberry-graphql
        pkgs.python3Packages.uvicorn
      ];
      NIX_LD_LIBRARY_PATH = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc
        pkgs.openssl
        pkgs.libz
        # ...
      ];
      NIX_LD = lib.fileContents "${pkgs.stdenv.cc}/nix-support/dynamic-linker";
      shellHook = ''
        export PANTS_SYSTEM_BINARIES_SYSTEM_BINARY_PATHS="$PATH"
        export PANTS_PROCESS_EXTRA_ENV='{"NIX_LD":"${NIX_LD}","NIX_LD_LIBRARY_PATH":"${NIX_LD_LIBRARY_PATH}"}'
      '';
    };
  };
}
