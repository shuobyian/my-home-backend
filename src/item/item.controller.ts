import { Body, Controller, Get, Post, Query } from '@nestjs/common';
import { CreateItemDto } from 'src/item/dto/create-item-dto';
import { ItemService } from 'src/item/item.service';

@Controller('item')
export class ItemController {
  constructor(private readonly itemService: ItemService) {}

  @Post()
  create(@Body() createItemDto: CreateItemDto) {
    return this.itemService.create(createItemDto);
  }

  @Get()
  findAll(@Query('page') page: number, @Query('size') size: number) {
    return this.itemService.findAllPage(page, size);
  }
}
