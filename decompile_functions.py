import subprocess
import os
import json
import re

def get_functions_list(so_path):
    print(f"Analisando símbolos de: {so_path}")
    # Usar rabin2 -sj para obter os símbolos em JSON
    try:
        result = subprocess.run(['rabin2', '-sj', so_path], capture_output=True, text=True, check=True)
        # O rabin2 pode retornar múltiplos objetos JSON se houver erros ou avisos, vamos tentar extrair o principal
        # Normalmente é uma lista direta de símbolos
        data = json.loads(result.stdout)
        
        functions = []
        # No rabin2 -sj, o resultado é uma lista direta de símbolos ou um objeto com a chave 'symbols'
        symbols = data if isinstance(data, list) else data.get('symbols', [])
        
        for sym in symbols:
            # Filtrar por tipo FUNC e garantir que não seja importado (queremos o código local)
            if sym.get('type') == 'FUNC' and sym.get('vaddr') and not sym.get('is_imported'):
                functions.append({
                    'name': sym.get('name'),
                    'vaddr': hex(sym.get('vaddr'))
                })
        return functions
    except Exception as e:
        print(f"Erro ao listar funções com rabin2: {e}")
        return []

def decompile_function(so_path, addr):
    # Executar radare2 para descompilar uma função específica via r2dec (pdd)
    try:
        # -qc executa comandos e sai. aa faz análise, pdd descompila.
        cmd = f"aa; pdd @ {addr}"
        result = subprocess.run(['r2', '-qc', cmd, so_path], capture_output=True, text=True, timeout=60)
        return result.stdout
    except subprocess.TimeoutExpired:
        return "/* Erro: Timeout na descompilação (30s excedidos) */"
    except Exception as e:
        return f"/* Erro na descompilação: {str(e)} */"

def main():
    files_dir = '/home/ubuntu/reverse-engineering/files'
    decomp_dir = '/home/ubuntu/reverse-engineering/decompiled'
    
    if not os.path.exists(decomp_dir):
        os.makedirs(decomp_dir)

    for filename in sorted(os.listdir(files_dir)):
        if filename.endswith('.so'):
            so_path = os.path.join(files_dir, filename)
            functions = get_functions_list(so_path)
            
            if not functions:
                print(f"Nenhuma função encontrada em {filename}")
                continue

            # Limitar para as 20 funções mais relevantes para não estourar limites de tempo/armazenamento
            limit = 20
            print(f"Descompilando as primeiras {limit} funções de {filename}...")
            
            output_file = os.path.join(decomp_dir, f"{filename}_pseudo.c")
            with open(output_file, 'w') as f:
                f.write(f"/* Pseudo-C gerado para {filename} */\n")
                f.write(f"/* Ferramenta: radare2 + r2dec */\n\n")
                
                for i, func in enumerate(functions[:limit]):
                    print(f"[{i+1}/{limit}] {func['name']} @ {func['vaddr']}")
                    pseudo_code = decompile_function(so_path, func['vaddr'])
                    f.write(f"// --- Função: {func['name']} @ {func['vaddr']} ---\n")
                    f.write(pseudo_code)
                    f.write("\n\n")
            
            print(f"Sucesso! Pseudo-C salvo em {output_file}")

if __name__ == "__main__":
    main()
