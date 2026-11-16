{
  description = "Tooling and CI checks for the educational 1C:Enterprise warehouse lab";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";

  outputs =
    { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" ];
      forEachSystem = f: nixpkgs.lib.genAttrs systems (system: f (import nixpkgs { inherit system; }));
    in
    {
      formatter = forEachSystem (pkgs: pkgs.nixfmt);

      devShells = forEachSystem (pkgs: {
        default = pkgs.mkShell {
          packages = with pkgs; [
            bash
            coreutils
            findutils
            gnugrep
            python3
            shellcheck
            shfmt
            actionlint
            nixfmt
            xvfb-run
          ];
          shellHook = ''
            echo "1C educational CI tools ready (the proprietary 1cv8t binary is installed separately)."
          '';
        };
      });

      checks = forEachSystem (pkgs: {
        static = pkgs.runCommand "1c-lab-static-checks" {
          nativeBuildInputs = with pkgs; [
            bash
            coreutils
            gnugrep
            python3
            shellcheck
            shfmt
            actionlint
          ];
        } ''
          cd ${self}
          shellcheck scripts/*.sh
          shfmt -ln=bash scripts/*.sh > /dev/null
          actionlint -config-file .github/actionlint.yaml .github/workflows/ci.yml
          PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
          test -s ./ФИНАЛЬНОЕ_ТЗ_1С_Тема_20_Контроль_неснижаемого_остатка.md
          mkdir -p "$out"
          touch "$out/passed"
        '';
      });

      apps = forEachSystem (pkgs: {
        validate-dt = {
          type = "app";
          program = "${pkgs.writeShellApplication {
            name = "validate-dt";
            runtimeInputs = with pkgs; [ bash coreutils findutils gnugrep xvfb-run ];
            text = ''
              exec bash ${self}/scripts/validate-dt.sh "$@"
            '';
          }}/bin/validate-dt";
        };
      });
    };
}
