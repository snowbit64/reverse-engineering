import subprocess
import os
import re

def extract_functions(so_path):
    print(f"Processando: {so_path}")
    
    # Usar readelf -Ws para listar todos os símbolos, incluindo dinâmicos
    # -W evita truncamento de nomes longos
    try:
        result = subprocess.run(['readelf', '-Ws', so_path], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Erro ao executar readelf em {so_path}: {e}")
        return []

    functions = []
    # Regex para capturar: Valor (Endereço), Tamanho, Tipo, Visibilidade, Índice da Seção, Nome
    # Exemplo: 3238: 000000000022f564   444 FUNC    GLOBAL DEFAULT   10 ov_bitrate
    pattern = re.compile(r'^\s*\d+:\s+([0-9a-fA-F]+)\s+\d+\s+FUNC\s+\w+\s+\w+\s+\d+\s+(.+)$')

    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match:
            addr = match.group(1)
            name = match.group(2)
            functions.append((addr, name))

    return functions

def demangle_names(names):
    if not names:
        return {}
    
    # Usar c++filt para fazer o demangle de nomes C++ (mangled)
    try:
        # Enviar todos os nomes de uma vez para o stdin do c++filt para performance
        process = subprocess.Popen(['c++filt'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        stdout, _ = process.communicate(input='\n'.join(names))
        demangled = stdout.splitlines()
        return dict(zip(names, demangled))
    except Exception as e:
        print(f"Erro ao executar c++filt: {e}")
        return {name: name for name in names}

def main():
    files_dir = '/home/ubuntu/reverse-engineering/files'
    output_dir = '/home/ubuntu/reverse-engineering/output'
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(files_dir):
        if filename.endswith('.so'):
            so_path = os.path.join(files_dir, filename)
            functions = extract_functions(so_path)
            
            if functions:
                names = [f[1] for f in functions]
                demangled_map = demangle_names(names)
                
                output_path = os.path.join(output_dir, f"{filename}_functions.txt")
                with open(output_path, 'w') as f:
                    f.write(f"# Funções extraídas de {filename}\n")
                    f.write(f"# {'Endereço':<18} | {'Nome Original':<40} | {'Nome Demangled'}\n")
                    f.write("-" * 100 + "\n")
                    for addr, name in functions:
                        d_name = demangled_map.get(name, name)
                        f.write(f"{addr:<18} | {name:<40} | {d_name}\n")
                
                print(f"Sucesso! {len(functions)} funções salvas em {output_path}")
            else:
                print(f"Nenhuma função encontrada com símbolos dinâmicos em {filename}")

if __name__ == "__main__":
    main()
