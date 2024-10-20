self: super: {
  python = super.python.override {
    packageOverrides = python-self: python-super: {
      hatchling = python-super.hatchling.overrideAttrs (oldAttrs: {
        src = super.fetchPypi {
          pname = "hatchling";
          version = "1.21.1";
          hash = "";
        };
      });
    };
  };
}
