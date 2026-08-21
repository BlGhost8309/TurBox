Файл post_template.txt содержит текст-шаблон для генерации поста Telegram.
В шаблоне можно использовать плейсхолдеры вида {field_name}, которые заменяются на соответствующие значения из каждого тура.

Доступные плейсхолдеры (названия полей из JSON подборки):

{hotel_name}                       – название отеля
{arrival_country}                  – страна прибытия
{departure_city}                   – город вылета
{price}                            – цена за тур (на двоих)
{nights}                           – количество ночей
{adults}                           – количество взрослых
{meal_type}                        – тип питания (например, "Всё включено")
{departure_date}                   – дата вылета (строка)
{return_date}                      – дата возврата
{book_url}                         – прямая ссылка на бронирование (onlinetours.ru/book/...)
{hotel_url}                        – ссылка на страницу отеля на onlinetours.ru
{stars}                            – звёздность отеля (число)
{rating}                           – рейтинг отеля на onlinetours.ru (из карточки)
{top_hotel_rating}                 – рейтинг отеля на TopHotels (из кэша)
{hotel_url_on_top_hotels}          – ссылка на страницу отеля на TopHotels
{price_per_night}                  – цена за ночь на двоих (price / nights)
{price_per_night_per_person}       – цена за ночь на одного (price / nights / adults)

Если в данных тура поле отсутствует (например, top_hotel_rating не был найден), плейсхолдер заменяется на пустую строку.

Пример шаблона (post_template.txt):

🏨 {hotel_name} {stars}*
📍 {arrival_country}, вылет из {departure_city}
📅 {departure_date} – {return_date} ({nights} ночей)
🍽️ Питание: {meal_type}
💰 {price} ₽ на двоих
🌟 Рейтинг onlinetours: {rating}
🏆 Рейтинг TopHotels: {top_hotel_rating}
🔗 Подробнее: {book_url}

После генерации поста все блоки (по одному на тур) склеиваются с двумя пустыми строками между ними.
