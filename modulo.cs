using System;
using System.IO;

namespace VoluntApp
{
    public static class Logger
    {
        //Ruta Logs
        private static string LogPath = "voluntapp.log";

        public static void Log(string mensaje)
        {
            try
            {
                //Si no existe el log
                if (!File.Exists(LogPath))
                {
                    FileStream archivoLog = File.Create(LogPath);
                    archivoLog.Close();
                }

                //Log
                var linea = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} - {mensaje}\n";
                
                //Introduce la linea al log
                StreamWriter writer = new StreamWriter(LogPath, append: true);
                writer.WriteLine(linea);

                writer.Close();
            }

            catch (Exception ex)
            {
                Console.Error.WriteLine($"Error al escribir en el log: {ex.Message}");
            }
        }
    }
}
