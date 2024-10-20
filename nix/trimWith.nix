{lib}: let
  trimWith = {
    start ? false,
    end ? false,
  }: let
    # Define our own whitespace character class instead of using
    # `[:space:]`, which is not well-defined.
    chars = " \t\r\n";

    # To match up until trailing whitespace, we need to capture a
    # group that ends with a non-whitespace character.
    regex =
      if start && end
      then "[${chars}]*(.*[^${chars}])[${chars}]*"
      else if start
      then "[${chars}]*(.*)"
      else if end
      then "(.*[^${chars}])[${chars}]*"
      else "(.*)";
  in
    s: let
      # If the string was empty or entirely whitespace,
      # then the regex may not match and `res` will be `null`.
      res = lib.match regex s;
    in
      lib.optionalString (res != null) (lib.head res);
in
  trimWith
