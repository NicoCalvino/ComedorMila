# kiosco_sole
Web para Administracion del Kiosco de un Colegio.

El kiosco funciona con tarjetas prepagas que las alumnas utilizan para comprar los productos.
Los usuarios de la pagina, ademas de los administradores, son los padres del colegio. Ellos daran de alta a sus hijos en el sistema para habilitarlos a consumir
Idealmente cada aluma tendría una sola tarjeta, pero se puede llegar a dar que por perdida o rotura, cada alumna tenga asociada mas de una tarjeta.

El proyecto tiene 7 clases: 
Cliente
Tarjeta
Producto
Transaccion
SolicitudCarga
DetalleCarga
Perfil

Pasos para probar el proyecto.

1) Luego de clonar el repositorio desde github, dirigirse a la carpeta del proyecto y ubicarse en el nivel donde este el archivo "manage.py"

2) crear el entorno virtual corriendo el siguiente comando

    python -m venv .venv

3) Activar el entorno virtual corriendo el siguiente comando

    .venv/Scripts/activate

4) Instalar los requerimientos del archivo requierements.txt corriendo el siguiente comando

    pip install -r requierements.txt

5) Levantar el servidor corriendo el siguiente comando 
    
    python manage.py runserver

6) Bajar el servidor utilizando el atajo "Ctrl+C"

7) Al levantar el servidor se tiene que haber creado el archivo "db.sqlite3" con migraciones pendientes. Correr los siguientes comandos para terminar de configurar la base de datos

    python manage.py makemigrations
    python manage.py migrate

8) Correr el siguiente comando para crear un superuser y poder tener acceso a la administracion del portal

    python manage.py createsuperuser

9) Volver a levantar el servidor corriendo el siguiente comando 
    
    python manage.py runserver

10) Abrir el vinculo http://127.0.0.1:8000 o localhost:8000

12) Cuando se entra al home, solo se muestra un formulario para logearse o registrarse ya que solo los usuarios de la pagina tienen acceso a la informacion de la pagina

13) Bajar hasta el footer y hacer click en el boton "Acerca de Mi".
    Se cargara una pagina con la informacion personal

14) Hacer click en "Comedor Mila" o "Home" en el navbar para volver al inicio

13) Hacer Click en "Quiero Registrarme" en el body o en "Registrarse" en el navbar y crearse un usuario
    Anotar el nombre de usuario elegido y la contraseña ya que posteriormente sera necesario volver a utilizarlos

14) Al crear el usuario, se logea automaticamente y seremos redirigidos a la pagina de nuestro perfil. Alli hacemos click en "Editar Perfil" y podremos modificar los siguientes items.
    - Nombre
    - Apellido
    - Mail
    - Celular
    - Dirección

    Para confirmar los cambios realizados debemos hacer click en "Guardar Cambios"

15) Desde "Editar Perfil" tambien podemos acceder a la pagina para cambiar nuestra contraseña. El boton se encuentra a la izquierda de los botones "Cancelar" y "Guardar Cambios"

16) Hacer click en "Comedor Mila" o "Home" en el navbar para volver al inicio

17) Hacer click en "Crear Cliente" en el navbar o "Crear mi primer cliente" en el body y completar un formulario para cargar un cliente. 
    Luego de crear el primer cliente, el home mostrara el cliente creado y un botón al lado para crear otro mas.
    Crear 2 clientes mas    

18) Entrar a los detalles de cualquiera de los clientes y hacer click en "Editar Cliente". Cambiar el nombre del cliente y hacer click en "Guardar Cliente"

19) Entrar a los detalles de otro cliente y hacer click en Eliminar. Saldrá un aviso preguntando si realmente queremos eliminar el cliente. Hacer click en "Si, eliminar cliente"

20) Hacer click en "Cerrar Sesion" en el navbar. Saldrá un mensaje preguntando si realmente queremos salir. Hacer click en "Si, Cerrar sesión".

21) Logearse ahora con las credenciales de superuser creado en el paso 8.
    Como al crear el superuser, no se completo "Nombre" y "Apellido", arriba a la derecha no aparecerá el nombre del usuario.
    Para corregir esto, hacemos click en el avatar (que seguramente sea la imagen por default) que nos llevara al pefil
    Alli luego ponemos "Editar Perfil" para completar la informacion que falte y posteriormente hacer click en "Guardar Cambios"

22) Hacer click en "Comedor Mila" o "Home" en el navbar para volver al inicio

23) Entrar a "Usuarios". Por defecto en la lista apareceran solo los usuarios "Normales", 
    Hacer click en "Superusuarios" para cambiar el filtro
    Hacer click en "Todos" para mostrar la lista completa

24) Probar la searchbar. La misma busca el texto indicado en el "username", "Nombre Completo" y "Email"

25) Hacer Click en "Ver Perfil" de un usuario normal. Notar que no aparece el boton para editar el perfil

26) Volver a la lista y Hacer Click en "Ver Perfil" del superusuer. Este si sera editable. Solo el dueño del perfil puede editarlo

27) Hacer click en "Clientes" en el navbar. Aparecerán los clientes creados por los usuarios comunes
    En la tercera columna aparecerá el nombre del usuario que creo el cliente.
    En la ultima columna aparecen los botones de accion para "Ver Detalles", "Editar" o "Eliminar" el cliente.
    Probar la searchbar. La misma busca el texto indicado en el nombre completo del cliente y en el nombre completo del usuario que lo creo

28) Hacer click en "Tarjetas" en el navbar. Hacer click en "Nueva Tarjeta" y completar el campo "Numero de tarjeta" con el siguiente numero

    501364000000001

    Hacer click en "Crear +" para dar de alta la tarjeta y volver a cargar el mismo formulario para crear otra tarjeta mas
    Deberia aparecer un mensaje informando la creacion exitosa de la tarjeta

29) Completar el campo "Numero de tarjeta" con el mismo numero del paso anterior y hacer click en "Crear".
    Debería tirar un error que informa que el codigo ya ha sido dado de alta

30) Cambiar por 501364000000002 y hacer click en "Crear +".

31) Cambiar por 501364000000003 y hacer click en "Crear". Deberia volver a la lista de tarjetas

32) Entrar al detalle de la primera tarjeta y ver que dice "Sin Alumna Asociada" arriba junto al boton para asociarle alguna alumna
    Hacer click en "Deshabilitar".
    Saldra un mensaje para confirmar que la queremos "Deshabilitar". Hacer click en OK
    Hacer click en "Volver al listado". El icono de la primera tarjeta tiene que haber cambiado a Rojo

33) Hacer click en "Eliminar" la tarjeta 501364000000002
    Saldra un mensaje para confirmar que la queremos "Eliminar". Hacer click en OK
    Volvera a cargar la lista ya sin esa tarjeta

33) Hacer click en "Asociar" la tarjeta 501364000000003
    Aparecera una lista con todos los clientes que han sido dados de alta.
    Tenemos un campo de Texto arriba por si queremos buscar algun cliente en particular
    Elegir uno y hacer click en asociar.
    Nos aparecera una pantalla para confirmar la asociacion. Hacer click en "Confirmar y Asociar"
    Nos devolvera al detalle de la tarjeta, ahora informando en la parte superior quien es su dueño

34) Utilizar el Campo "Buscar" de la parte superior para probar las siguientes busquedas (los numeros buscados se buscan solo en los ultimos 9 digitos del codigo de tarjeta)
    Ademas tenemos la opcion de filtrar por las tarjetas que tienen Clientes, las que no tienen Cliente o Todas

35) Hacer click en "Transacciones" en el navbar

36) Hacer click en "Cargar Saldo", completar el monto con $ 3500 y luego hacer las siguientes pruebas
    Completar el numero de tarjeta con 501364000000001 y hacer click en cargar saldo. Tiene que aparecer un mensaje informando que la no esta habilitada
    Completar el numero de tarjeta con 501364000000002 y hacer click en cargar saldo. Tiene que aparecer un mensaje informando que la tarjeta no existe
    Completar el numero de tarjeta con 501364000000003 y hacer click en cargar saldo. Tiene que hacer la carga correctamente y redirigirnos al detalle de la tarjeta

37) Desde el detalle de la tarjeta, hacer click en "Cargar Saldo", nos deberia llevar a la misma pantalla que antes, pero esta vez el numero de tarjeta ya estara completo.

38) Hacer click en "Transacciones" en el navbar

39) Hacer click en "Nueva Compra", completar el monto con $ 1500 y el numero de tarjeta 501364000000003.
    Hacer click en "Confirmar Compra", deberia aparecer un mensaje informando que la compra ha sido exitosa y volver a cargarnos la misma pantalla para cargar otra mas 

38) Hacer click en "Transacciones" en el navbar y ver que en la lista aparecen las dos transacciones que hicimos recien
    Las transacciones se pueden filtrar por "TODO", "CARGAS" y "COMPRAS"

39) Entrar a "ver el detalle" de alguna de las transacciones

40) Hacer click en "Tarjetas", ver que en la tarjeta 501364000000003 el saldo deberia ser de $ 2000 (+3500 - 1500)

41) Hacer click en "Transacciones" en el navbar

42) Hacer click en "Nueva Compra", completar el monto con $ 5000 y el numero de tarjeta 501364000000003.
    Hacer click en "Confirmar Compra", deberia aparecer un mensaje de error informando que el saldo en insuficiente
    Cambiar el monto a $ 4000 y hacer click en "Confirmar Compra", esta vez deberia dejarnos ya que se permite un giro en descubierto de -$ 2000

43) Hacer click en "Tarjetas", ver que en la tarjeta 501364000000003 el saldo deberia ser de -$ 2000 (+3500 - 1500 - 4000)

44) Hacer click en "Transacciones" en el navbar

45) Entrar a "Ver Detalle" de la ultima compra por $ 4000 y luego hacer click en "Eliminar"
    Aparecerá un mensaje pidiendonos que confirmemos si queremos eliminarla. Hacer Click en "Confirmar Eliminacion"
    Nos llevara nuevamente a la lista de transacciones y ya no aparecera la compra

46) Hacer click en "Tarjetas", ver que en la tarjeta 501364000000003 el saldo deberia ser nuevamente de $ 2000 (+3500 - 1500 - 4000 + 4000)

47) Hacer click en "Transacciones" en el navbar

48) Entrar a "Ver Detalle" de la carga de saldo por $ 3500 y luego hacer click en "Editar"
    Cambiar el monto de carga a $ 4000 y luego hacer click en "Guardar Cambios"
    Nos llevara nuevamente a la lista de transacciones con la transaccion actualizada

49) Hacer click en "Tarjetas", ver que en la tarjeta 501364000000003 el saldo deberia ser de $ 2500 (+3500 - 1500 - 4000 + 4000 - 3500 + 4000)

50) Hacer click en "Productos" en el navbar y luego hacer click en "Nuevo"

51) Crear un producto. Luego de completar la informacion, se pueden clickear dos botones

    "Guardar y Volver" - Crea el producto y nos lleva a la pagina del detalle del mismo
    "Guardar y Crear Otro" - Nos da un mensaje de que el producto se ha creado exitosamente y nos carga el formulario para dar de alta otro producto mas

    Hacer primero un producto utilizando la opcion "Guardar y Crear Otro" y luego uno haciendo click en "Guardar y Volver"

52) Desde el detalle del producto hacer click en "Editar"
    Nos abrira el formulario de edicion del producto. Hacer un cambio en algun campo y luego hacer click en "Guardar Cambios"
    Nos llevara nuevamente al detalle del producto

53) Hacer click en "Volver al listado"

54) Veremos la lista de productos la cual podemos ordenar por "Nombre", "Marca", "Categoria" o "Precio" haciendo click en el titul
    Tambien podemos utilizar la barra de busqueda la cual buscara el texto en los campos "Nombre", "Marca" y "Categoria"

55) Hacer click en cerrar sesion y volver a logearse como usuario comun

56) Desde el home podemos entrar al Cliente dueño de la tarjeta 501364000000003 y apareceran todas las transacciones realizadas con la misma.
    Tambien podemos habilitar o deshabilitar la tarjeta desde aqui

57) Hacer click en "Cargar Saldo" en el navbar y luego hacer click en "Nueva Solicitud"
    Completar el monto que queremos cargarle a cada tarjeta y luego adjuntar un comprobante de pago
    Hacer Click en enviar solicitud y nos devolvera a la lista de solicitudes deonde podremos ver la que acabamos de crear

58) Hacer click nuevamente en "Nueva Solicitud" y cargar otra mas
    Hacer Click en enviar solicitud y nos devolvera a la lista de solicitudes deonde podremos ver la que acabamos de crear

59) Entrar a "Ver Detalle" de la ultima solicitud cargada y luego hacer click en "Cancelar Solicitud"
    Nos aparecera un mensaje para confirmar que queremos eliminarla
    Hacer click en "Confirmar Eliminacion" y nos llevara de vuelta a la lista ya sin la Solicitud eliminada

60) Entrar a "Editar" la solicitud cargada, Editar cualquiera de los montos y luego hacer click en "Confirmar Edicion"
    Nos llevara de vuelta a la lista con los cambios hechos

61) Hacer click en cerrar sesion y volver a logearse como superuser

62) Hacer click en "Solicitudes de Carga" en el navbar
    Nos aparecera una lista con todas las solicitudes hechas.
    Podemos filtrar las solicitudes por "APROBADAS", "RECHAZADAS", "PENDIENTES" y "TODAS"
    Tambien podemos utilizar la barra de busqueda para buscar las solicitudes por usuario
    
63) Entrar al detalle de una solicitud y Aprobar la misma.
    Si luego revisamos el saldo de las tarjetas implicadas, podemos ver que su monto ha aumentado

64) Si nos volvemos a logear desde el usuario podemos ver que se ha actualizado el estado de nuestra solicitud y solo nos dejaria editar aquellas que estan pendientes.