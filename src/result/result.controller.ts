import { Controller, Get, Post, Query } from '@nestjs/common';
import { ResultService } from 'src/result/result.service';

@Controller('result')
export class ResultController {
  constructor(private readonly resultService: ResultService) {}

  @Post()
  createAll() {
    return this.resultService.createAll();
  }

  @Get()
  findAll(
    @Query('page') page: number,
    @Query('size') size: number,
    @Query('name') name?: string,
    @Query('count') count?: number,
  ) {
    return this.resultService.findAllPage(page, size, name, count);
  }
}
