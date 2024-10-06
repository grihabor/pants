{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.11";
    pants-nix = {
      url = "github:grihabor/pants-nix/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    self,
    nixpkgs,
    pants-nix,
  }: let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
    lib = nixpkgs.lib;
  in {
    devShells."x86_64-linux".default = pkgs.mkShell rec {
      packages = [
        pants-nix.packages."x86_64-linux"."release_2.21.0"
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
