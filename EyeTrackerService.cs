using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using StreamEngineDemo.Models;
using Tobii.StreamEngine;

namespace StreamEngineDemo.Services
{
    public class EyeTrackerService
    {
        private static IntPtr _apiContext;
        private static IntPtr _deviceContext;
        private static List<GazeData> _gazePoints = new List<GazeData>();
        private static CancellationTokenSource _cts;
        private static bool _isRunning = false;
        private static tobii_gaze_point_callback_t _gazeCallback;


        public static IReadOnlyList<GazeData> GazePoints => _gazePoints;
        public static bool IsRunning => _isRunning;

        public static void Start()
        {
            if (_isRunning)
            {
                Console.WriteLine("Registrazione già in corso.");
                return;
            }


            _gazePoints.Clear();
            _cts = new CancellationTokenSource();
            _isRunning = true;

            // Crea contesto e device
            var result = Interop.tobii_api_create(out _apiContext, null);
            Debug.Assert(result == tobii_error_t.TOBII_ERROR_NO_ERROR);

            result = Interop.tobii_enumerate_local_device_urls(_apiContext, out var urls);
            Debug.Assert(result == tobii_error_t.TOBII_ERROR_NO_ERROR);
            if (urls.Count == 0) throw new Exception("Nessun eye tracker trovato.");

            result = Interop.tobii_device_create(_apiContext, urls[0], Interop.tobii_field_of_use_t.TOBII_FIELD_OF_USE_STORE_OR_TRANSFER_FALSE, out _deviceContext);
            Debug.Assert(result == tobii_error_t.TOBII_ERROR_NO_ERROR);

            _gazeCallback = new tobii_gaze_point_callback_t(OnGazePoint);
            result = Interop.tobii_gaze_point_subscribe(_deviceContext, _gazeCallback);
            //Debug.Assert(result == tobii_error_t.TOBII_ERROR_NO_ERROR);

            // Avvio thread di acquisizione
            ThreadPool.QueueUserWorkItem(_ =>
            {
                var token = _cts.Token;
                Console.WriteLine("Registrazione iniziata.");

                while (!token.IsCancellationRequested)
                {
                    result = Interop.tobii_wait_for_callbacks(new[] { _deviceContext });
                    if (result == tobii_error_t.TOBII_ERROR_TIMED_OUT) continue;

                    result = Interop.tobii_device_process_callbacks(_deviceContext);
                }

                Console.WriteLine("Registrazione interrotta.");
            });
        }

        public static void Stop()
        {
            if (!_isRunning) return;

            _cts?.Cancel();
            Thread.Sleep(200); // attesa minima per sicurezza

            Interop.tobii_gaze_point_unsubscribe(_deviceContext);
            Interop.tobii_device_destroy(_deviceContext);
            Interop.tobii_api_destroy(_apiContext);

            _gazeCallback = null;
            _isRunning = false;

        }

        private static void OnGazePoint(ref tobii_gaze_point_t gazePoint, IntPtr userData)
        {
            if (gazePoint.validity == tobii_validity_t.TOBII_VALIDITY_VALID)
            {
                _gazePoints.Add(new GazeData
                {
                    X = gazePoint.position.x,
                    Y = gazePoint.position.y,
                    Timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()
                });
            }
        }
    }

}
